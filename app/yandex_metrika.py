import requests
import logging
from datetime import datetime, timedelta
import backoff

logger = logging.getLogger(__name__)

class YandexMetrikaAPI:
    def __init__(self, oauth_token):
        self.oauth_token = oauth_token
        self.base_url = "https://api-metrika.yandex.net/stat/v1/data"

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
    def _make_request(self, params):
        """Выполняет запрос к API с автоматическим повтором при ошибках"""
        headers = {"Authorization": f"OAuth {self.oauth_token}"}
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to Metrika API: {str(e)}")
            raise

    def get_traffic_data(self, counter_id, urls):
        """Получает данные о трафике для списка URL"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        
        traffic_data = {}
        for url in urls:
            try:
                params = {
                    'ids': counter_id,
                    'metrics': 'ym:s:users',
                    'dimensions': 'ym:s:date',
                    'filters': f"ym:s:startURL=='{url}'",
                    'date1': start_date.strftime('%Y-%m-%d'),
                    'date2': end_date.strftime('%Y-%m-%d'),
                    'limit': 10000
                }
                
                data = self._make_request(params)
                
                if 'data' in data:
                    # Собираем данные по дням
                    daily_data = []
                    for row in data['data']:
                        date = datetime.strptime(row['dimensions'][0]['name'], '%Y-%m-%d').date()
                        visitors = row['metrics'][0]
                        daily_data.append((date, visitors))
                    
                    # Сортируем по дате
                    daily_data.sort(key=lambda x: x[0])
                    
                    # Вычисляем среднее количество посетителей
                    if daily_data:
                        avg_visitors = sum(visitors for _, visitors in daily_data) / len(daily_data)
                        date_range = f"{start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}"
                        traffic_data[url] = (avg_visitors, date_range)
                        continue
                
                logger.warning(f"No traffic data found for URL: {url}")
                traffic_data[url] = (0, None)
                
            except Exception as e:
                logger.error(f"Error getting traffic for URL '{url}': {str(e)}")
                traffic_data[url] = (0, None)
        
        return traffic_data

    def validate_counter(self, counter_id):
        """Проверяет доступность счетчика в Яндекс.Метрике"""
        try:
            params = {
                'ids': counter_id,
                'metrics': 'ym:s:users',
                'date1': 'today',
                'date2': 'today',
                'limit': 1
            }
            self._make_request(params)
            return True
        except requests.exceptions.RequestException:
            return False
