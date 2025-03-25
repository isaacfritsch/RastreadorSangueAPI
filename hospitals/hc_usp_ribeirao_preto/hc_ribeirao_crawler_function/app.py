import json
import boto3
import requests
from datetime import datetime
from ribeirao_blood_center_crawler import BloodChartExtractor,BloodStockCrawler, parse_blood_supply
import re

MAIN_URL = "https://www.hemocentro.fmrp.usp.br/canal-do-doador/estoque-de-sangue/"


def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('hospitals_blood_status')

    crawler = BloodStockCrawler(MAIN_URL)
    chart_extractor = BloodChartExtractor(crawler.session)

    docs_links = crawler.get_google_docs_links()

    for cidade, doc_url in docs_links.items():
        try:
            chart_data = chart_extractor.get_chart_data(doc_url)
            blood_supply = parse_blood_supply(chart_data)

            print(f"{cidade} - Estoque de Sangue: {blood_supply}")

            table.put_item(
                Item={
                    'hospital': cidade.lower().replace(" ", "_"),
                    'date': datetime.now().isoformat(),
                    'a_plus_status': blood_supply['A+'],
                    'a_minus_status': blood_supply['A-'],
                    'b_plus_status': blood_supply['B+'],
                    'b_minus_status': blood_supply['B-'],
                    'ab_plus_status': blood_supply['AB+'],
                    'ab_minus_status': blood_supply['AB-'],
                    'o_plus_status': blood_supply['O+'],
                    'o_minus_status': blood_supply['O-'],
                }
            )

        except Exception as e:
            print(f"Erro ao processar {cidade}: {e}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hc_usp_ribeirao blood supply status updated successfully.",
        }),
    }