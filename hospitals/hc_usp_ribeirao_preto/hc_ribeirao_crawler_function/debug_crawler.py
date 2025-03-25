from ribeirao_blood_center_crawler import BloodStockCrawler, BloodChartExtractor, parse_blood_supply
from app import lambda_handler
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

MAIN_URL = "https://www.hemocentro.fmrp.usp.br/canal-do-doador/estoque-de-sangue/"

def debug_lambda_handler():
    # Mock de todas as dependências
    with patch('app.boto3.resource') as mock_boto, \
         patch('app.BloodStockCrawler') as mock_crawler, \
         patch('app.BloodChartExtractor') as mock_extractor:

        # Configurar mocks
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table
        
        # Mock do crawler
        mock_crawler_instance = MagicMock()
        mock_crawler_instance.get_google_docs_links.return_value = {
            "Hc_usp_ribeirao": "https://fake-url.com"
        }
        mock_crawler.return_value = mock_crawler_instance
        
        # Mock do extractor
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.get_chart_data.return_value = {
            "dataTable": {
                "rows": [
                    {"c": [{"v": "A+"}, {"v": 100}, {"v": 50}]}
                ]
            }
        }
        mock_extractor.return_value = mock_extractor_instance

        # Executar handler
        from app import lambda_handler
        result = lambda_handler(None, None)

        # Verificar saída
        print("\n=== Resultado ===")
        print(f"Status Code: {result['statusCode']}")
        print(f"Body: {result['body']}")

        # Verificar chamada no DynamoDB
        mock_table.put_item.assert_called_once()
        print("\n=== Dados gravados ===")
        print(json.dumps(mock_table.put_item.call_args[1]['Item'], indent=2))

if __name__ == "__main__":
    debug_lambda_handler()