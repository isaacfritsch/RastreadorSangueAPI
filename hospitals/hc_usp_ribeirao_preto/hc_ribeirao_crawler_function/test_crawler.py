import unittest
from unittest.mock import MagicMock, patch
import requests
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
# Importe suas classes aqui (ajuste o caminho conforme necessário)
from ribeirao_blood_center_crawler import (
    BloodStockCrawler,
    BloodChartExtractor,
    parse_blood_supply,
    MAIN_URL
)

class TestBloodStockCrawler(unittest.TestCase):
    
    @patch("ribeirao_blood_center_crawler.requests.Session.get")
    def test_get_google_docs_links(self, mock_get):
        """Testa a extração de links do Google Docs"""
        # Configurar mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
            <a href="https://docs.google.com/spreadsheets/d/123">São Paulo</a>
            <a href="https://docs.google.com/spreadsheets/d/456">Rio de Janeiro</a>
        """
        mock_get.return_value = mock_response

        # Executar
        crawler = BloodStockCrawler(MAIN_URL)
        result = crawler.get_google_docs_links()

        # Verificar
        expected = {
            "São Paulo_hcusp_rede_ribeirao_preto": "https://docs.google.com/spreadsheets/d/123",
            "Rio de Janeiro_hcusp_rede_ribeirao_preto": "https://docs.google.com/spreadsheets/d/456"
        }
        self.assertEqual(result, expected)

class TestBloodChartExtractor(unittest.TestCase):

    def setUp(self):
        self.mock_session = MagicMock()
        self.extractor = BloodChartExtractor(self.mock_session)

    
    @patch("requests.Session.get")
    def test_get_chart_data_success(self, mock_get):
        """Testa a extração correta do chartJson"""
        # Configurar mock da resposta HTTP
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # JSON válido e corretamente escapado
        valid_json = r'{"dataTable": {"rows": [{"c": [{"v": "A+"}, {"v": 68}, {"v": 68}]}]}}'
        
        mock_response.text = f"""
        <html>
            <script nonce="tOUFrLZd98xMnNe_Iq_xhg">
                var chartData = {{ }};
                chartData['chart'] = null;
                function initCharts() {{
                    chartData['chart'] = {{
                        'chartId': 'chart',
                        'elementId': 'embed_chart',
                        'chartJson': '{valid_json.replace('"', r'\"')}'
                    }};
                }}
            </script>
        </html>
        """
        mock_get.return_value = mock_response

        # Executar
        extractor = BloodChartExtractor(requests.Session())
        result = extractor.get_chart_data("https://fake-url.com")

        # Verificar
        self.assertIn("dataTable", result)
        self.assertIn("rows", result["dataTable"])
        
        
    def test_get_chart_data_missing_json(self):
        """Testa o tratamento de JSON ausente"""
        # Configurar mock sem chartJson
        self.mock_session.get.return_value = MagicMock(
            status_code=200,
            text="<html><script>var x = 1;</script></html>"
        )
        
        # Executar e verificar exceção
        with self.assertRaises(Exception):
            self.extractor.get_chart_data("https://bad-url.com")

class TestParseBloodSupply(unittest.TestCase):
    def test_parse_blood_supply_valid_data(self):
        """Testa o parser com dados válidos"""
        chart_data = {
            "dataTable": {
                "rows": [
                    {"c": [{"v": "A+"}, {"v": 68}, {"v": 68}]},
                    {"c": [{"v": "A-"}, {"v": 5}, {"v": 8}]},
                    {"c": [{"v": "B+"}, {"v": 87}, {"v": 10}]},
                    {"c": [{"v": "B-"}, {"v": 23}, {"v": 2}]},
                    {"c": [{"v": "AB+"}, {"v": 2726}, {"v": 2}]},
                    {"c": [{"v": "AB-"}, {"v": 6}, {"v": 3}]},
                    {"c": [{"v": "O+"}, {"v": 86}, {"v": 80}]},
                    {"c": [{"v": "O-"}, {"v": 13}, {"v": 18}]}
                ]
            }
        }

        result = parse_blood_supply(chart_data)

        expected = {
            "A+": "STABLE",
            "A-": "CRITICAL",
            "B+": "STABLE",
            "B-": "STABLE",
            "AB+": "STABLE",
            "AB-": "STABLE",
            "O+": "STABLE",
            "O-": "CRITICAL"
        }
        self.assertEqual(result, expected)

    def test_parse_blood_supply_empty_data(self):
        """Testa o parser com dados vazios"""
        chart_data = {
            "dataTable": {
                "rows": []
            }
        }

        result = parse_blood_supply(chart_data)

        expected = {
            "A+": "unknown",
            "A-": "unknown",
            "B+": "unknown",
            "B-": "unknown",
            "AB+": "unknown",
            "AB-": "unknown",
            "O+": "unknown",
            "O-": "unknown"
        }
        self.assertEqual(result, expected)

    def test_empty_data(self):
        """Testa o parser com dados vazios"""
        result = parse_blood_supply({"data": {"rows": []}})
        
        expected = {k: "unknown" for k in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]}
        self.assertEqual(result, expected)

class TestLambdaHandler(unittest.TestCase):

    @patch("ribeirao_blood_center_crawler.boto3.resource")
    @patch("ribeirao_blood_center_crawler.BloodStockCrawler")
    @patch("ribeirao_blood_center_crawler.BloodChartExtractor")
    def test_lambda_handler_success(self, mock_extractor, mock_crawler, mock_boto):
        """Testa o fluxo completo do Lambda"""
        # Configurar mocks
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        mock_crawler_instance = MagicMock()
        mock_crawler_instance.get_google_docs_links.return_value = {
            "Campinas": "https://docs.google.com/fake-link"
        }
        mock_crawler.return_value = mock_crawler_instance

        mock_extractor_instance = MagicMock()
        mock_extractor_instance.get_chart_data.return_value = {
            "dataTable": {
                "rows": [
                    {"c": [{"v": "A+"}, {"v": 68}, {"v": 68}]},
                    {"c": [{"v": "B-"}, {"v": 23}, {"v": 2}]}
                ]
            }
        }
        mock_extractor.return_value = mock_extractor_instance

        # Executar
        from app import lambda_handler
        response = lambda_handler(None, None)

        # Verificar
        self.assertEqual(response["statusCode"], 200)
        mock_table.put_item.assert_called()

if __name__ == "__main__":
    unittest.main()