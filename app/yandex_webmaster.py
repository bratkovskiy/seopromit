import requests
import logging
from datetime import datetime, timedelta
import backoff

logger = logging.getLogger(__name__)

class YandexWebmasterAPI:
    def __init__(self, oauth_token, user_id):
        self.oauth_token = oauth_token
        self.user_id = user_id
        self.base_url = "https://api.webmaster.yandex.net/v4/user"

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
    def _make_request(self, method, endpoint, **kwargs):
        """Выполняет запрос к API с автоматическим повтором при ошибках"""
        url = f"{self.base_url}/{self.user_id}/{endpoint}"
        headers = {"Authorization": f"OAuth {self.oauth_token}"}
        
        if 'headers' in kwargs:
            kwargs['headers'].update(headers)
        else:
            kwargs['headers'] = headers

        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to {endpoint}: {str(e)}")
            raise

    def get_keywords_positions(self, host_url, keywords, date_from=None, date_to=None):
        """Получает позиции для списка ключевых слов"""
        if date_from is None or date_to is None:
            date_to = datetime.now().date()
            date_from = date_to - timedelta(days=6)
        
        positions = {}
        for keyword in keywords:
            try:
                # Получаем ID хоста из URL
                hosts_response = self._make_request('GET', 'hosts')
                host_id = None
                for host in hosts_response['hosts']:
                    if host['ascii_host_url'] == host_url:
                        host_id = host['host_id']
                        break
                
                if not host_id:
                    logger.error(f"Host ID not found for URL: {host_url}")
                    positions[keyword] = (None, None)
                    continue

                data = self._make_request(
                    'POST',
                    f"hosts/{host_id}/query-analytics/list",
                    json={
                        "filters": {
                            "text_filters": [{
                                "text_indicator": "QUERY",
                                "operation": "TEXT_MATCH",
                                "value": keyword
                            }]
                        },
                        "sort_by_date": {
                            "date": date_from.strftime("%Y-%m-%d"),
                            "statistic_field": "IMPRESSIONS",
                            "by": "ASC"
                        }
                    }
                )

                if 'text_indicator_to_statistics' in data:
                    stats = data['text_indicator_to_statistics']
                    if stats:
                        position_data = next(
                            (stat for stat in stats if stat['text_indicator']['value'] == keyword),
                            None
                        )
                        if position_data:
                            position_stats = position_data['statistics']
                            position_entries = [
                                entry for entry in position_stats
                                if entry['field'] == 'POSITION'
                            ]
                            if position_entries:
                                # Сортируем по дате и берем последние 7 дней
                                sorted_entries = sorted(
                                    position_entries,
                                    key=lambda x: x['date'],
                                    reverse=True
                                )[:7]
                                
                                # Вычисляем среднюю позицию
                                positions_values = [entry['value'] for entry in sorted_entries]
                                avg_position = sum(positions_values) / len(positions_values)
                                
                                # Формируем диапазон дат
                                date_range = f"{date_from.strftime('%d.%m')} - {date_to.strftime('%d.%m')}"
                                
                                positions[keyword] = (avg_position, date_range)
                                continue

                logger.warning(f"No position data found for keyword: {keyword}")
                positions[keyword] = (None, None)

            except Exception as e:
                logger.error(f"Error getting position for keyword '{keyword}': {str(e)}")
                positions[keyword] = (None, None)

        return positions

    def validate_host(self, host_id):
        """Проверяет доступность хоста в Яндекс.Вебмастер"""
        try:
            data = self._make_request('GET', f"hosts/{host_id}")
            return True
        except requests.exceptions.RequestException:
            return False
