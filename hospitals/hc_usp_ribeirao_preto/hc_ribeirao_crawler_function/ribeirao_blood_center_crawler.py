import json
import boto3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

MAIN_URL = "https://www.hemocentro.fmrp.usp.br/canal-do-doador/estoque-de-sangue/"

class BloodStockCrawler:
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()

    def get_google_docs_links(self):
        response = self.session.get(self.url)
        if response.status_code != 200:
            raise Exception(f"Erro ao acessar a página: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        docs_links = {}
        for link in soup.find_all("a", href=True):
            if "docs.google.com/spreadsheets" in link["href"]:
                cidade = link.get_text(strip=True)
                if cidade == "Franca":
                    string = link["href"] 
                    docs_links[cidade] = string.replace("image","interactive")
                    continue
                docs_links[cidade + '_hcusp_rede_ribeirao_preto'] = link["href"]
        return docs_links

class BloodChartExtractor:
    def __init__(self, session):
        self.session = session

    def get_chart_data(self, doc_url):
        """Extrai a string JSON do gráfico do Google Docs"""
        response = self.session.get(doc_url)
        if response.status_code != 200:
            raise Exception(f"Erro ao acessar o Google Docs: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        # Buscar o script que contém "chartJson"
        script_tags = soup.find_all("script", string=lambda t: t and "chartJson" in t)
        if not script_tags:
            raise Exception("Não foi possível encontrar o JSON do gráfico.")

        # Extrair o conteúdo do script
        script_content = script_tags[0].string

        # Expressão regular para capturar o conteúdo de "chartJson"
        match = re.search(r"'chartJson':\s*'([^']+)'", script_content)
        if not match:
            raise Exception("Não foi possível extrair a string do chartJson.")

        chart_json_str = match.group(1)  # Pegamos apenas a string dentro das aspas

        # Decodificar caracteres de escape (\x7b, \x22 etc.)
        try:
            chart_json_decoded = bytes(chart_json_str, "utf-8").decode("unicode_escape")
            chart_data = json.loads(chart_json_decoded)
        except Exception as e:
            raise Exception(f"Erro ao decodificar ou parsear o JSON: {e}")

        return chart_data

def parse_blood_supply(chart_data):
    """Converte os dados extraídos no formato correto"""
    blood_supply = {
        "A+": "unknown",
        "A-": "unknown",
        "B+": "unknown",
        "B-": "unknown",
        "AB+": "unknown",
        "AB-": "unknown",
        "O+": "unknown",
        "O-": "unknown"
    }

    # Extrair as linhas da tabela
    rows = chart_data.get("dataTable", {}).get("rows", [])

    for row in rows:
        cells = row.get("c", [])
        if len(cells) >= 3:  # Verifica se há pelo menos 3 colunas
            blood_type = cells[0].get("v", "").strip().upper()  # Tipo sanguíneo
            stock_value = cells[1].get("v", 0)  # Situação do estoque
            min_stock = cells[2].get("v", 0)  # Estoque mínimo de segurança

            # Determinar o status com base na comparação entre estoque e mínimo
            if stock_value < min_stock:
                status = "CRITICAL"
            else:
                status = "STABLE"

            # Atualizar o dicionário de tipos sanguíneos
            if blood_type in blood_supply:
                blood_supply[blood_type] = status

    return blood_supply