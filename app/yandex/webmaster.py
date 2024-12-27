import requests
from flask import current_app

class YandexWebmasterAPI:
    BASE_URL = 'https://api.webmaster.yandex.net/v4'
    
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': f'OAuth {token}',
            'Content-Type': 'application/json'
        }
    
    def get_host_id(self, host_url, user_id):
        """Получает host_id по URL хоста"""
        try:
            api_url = f'{self.BASE_URL}/user/{user_id}/hosts'
            current_app.logger.info(f"Получаем список хостов с {api_url}")
            
            response = requests.get(api_url, headers=self.headers)
            if response.status_code != 200:
                current_app.logger.error(f"Ошибка при получении списка хостов: {response.status_code}")
                return None
            
            hosts_data = response.json()
            for host in hosts_data.get('hosts', []):
                if host.get('ascii_host_url') == host_url:
                    host_id = host.get('host_id')
                    current_app.logger.info(f"Найден host_id: {host_id} для {host_url}")
                    return host_id
            
            current_app.logger.warning(f"Хост {host_url} не найден в списке")
            return None
        except Exception as e:
            current_app.logger.error(f"Ошибка при получении host_id: {str(e)}")
            return None

    def validate_host(self, host_url, user_id):
        """Проверяет доступность хоста в Вебмастере"""
        try:
            current_app.logger.info(f"\n=== Проверка хоста {host_url} для user_id {user_id} ===")
            
            # Используем тот же URL что и в рабочем скрипте
            api_url = f'{self.BASE_URL}/user/{user_id}/hosts/{host_url}/query-analytics/list'
            current_app.logger.info(f"Отправляем запрос к: {api_url}")
            
            # Используем те же параметры что и в рабочем скрипте
            params = {
                "operation": "TEXT_CONTAINS",
                "limit": "1"  # Нам нужен только один результат для проверки
            }
            
            response = requests.post(api_url, json=params, headers=self.headers)
            current_app.logger.info(f"Статус ответа: {response.status_code}")
            current_app.logger.info(f"Текст ответа: {response.text[:500]}")
            
            if response.status_code == 200:
                return True, "Хост успешно подключен в Яндекс.Вебмастере"
            elif response.status_code == 404:
                return False, "Указанный хост не найден в Яндекс.Вебмастере"
            else:
                error_msg = f"Ошибка при проверке хоста: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error_message' in error_data:
                        error_msg += f" - {error_data['error_message']}"
                    elif 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f'Ошибка при проверке хоста в Вебмастере: {str(e)}'
            current_app.logger.error(error_msg)
            return False, error_msg
