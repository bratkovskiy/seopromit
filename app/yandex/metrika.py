import requests
from flask import current_app

class YandexMetrikaAPI:
    BASE_URL = 'https://api-metrika.yandex.net/management/v1'
    
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'OAuth {token}',
            'Content-Type': 'application/json'
        }
    
    def validate_counter(self, counter_id):
        """Проверяет доступность счетчика Метрики"""
        try:
            response = requests.get(
                f'{self.BASE_URL}/counter/{counter_id}',
                headers=self.headers
            )
            if response.status_code == 200:
                return True, "Счетчик Яндекс.Метрики успешно подключен"
            elif response.status_code == 403:
                return False, "Ошибка доступа: проверьте права токена Яндекс.Метрики"
            else:
                return False, f"Ошибка подключения к Яндекс.Метрике: {response.json().get('message', 'Неизвестная ошибка')}"
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Ошибка при проверке счетчика Метрики: {str(e)}')
            return False, "Ошибка подключения к API Яндекс.Метрики"
