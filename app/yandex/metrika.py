import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)

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
        logger.info(f"Начало валидации счетчика Метрики {counter_id}")
        try:
            logger.info(f"Отправка запроса к API Метрики для счетчика {counter_id}")
            response = requests.get(
                f'{self.BASE_URL}/counter/{counter_id}',
                headers=self.headers
            )
            logger.info(f"Получен ответ от API Метрики: статус {response.status_code}")
            logger.info(f"Тело ответа: {response.text[:200]}...")  # Логируем первые 200 символов
            
            if response.status_code == 200:
                logger.info("Валидация счетчика Метрики успешна")
                return True, "Счетчик Яндекс.Метрики успешно подключен"
            elif response.status_code == 403:
                logger.error("Ошибка доступа к API Метрики: 403")
                return False, "Ошибка доступа: проверьте права токена Яндекс.Метрики"
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', 'Неизвестная ошибка')
                except:
                    error_msg = response.text or 'Неизвестная ошибка'
                
                logger.error(f"Ошибка при валидации счетчика: {error_msg}")
                return False, f"Ошибка подключения к Яндекс.Метрике: {error_msg}"
                
        except requests.exceptions.RequestException as e:
            error_msg = f'Ошибка при проверке счетчика Метрики: {str(e)}'
            logger.error(error_msg)
            return False, "Ошибка подключения к API Яндекс.Метрики"

    def get_pageviews(self, counter_id: str, start_date: str, end_date: str, filters: str = None) -> int:
        """
        Получает количество просмотров страницы за указанный период
        
        Args:
            counter_id: ID счетчика Метрики
            start_date: Начальная дата в формате YYYY-MM-DD
            end_date: Конечная дата в формате YYYY-MM-DD
            filters: URL страницы для фильтрации
        
        Returns:
            Количество просмотров или None в случае ошибки
        """
        try:
            url = f'https://api-metrika.yandex.net/stat/v1/data'
            params = {
                'ids': counter_id,
                'metrics': 'ym:pv:pageviews',
                'dimensions': 'ym:pv:URLPath',
                'date1': start_date,
                'date2': end_date,
                'limit': 1
            }
            
            if filters:
                # Используем фильтр как есть, так как он уже в правильном формате
                params['filters'] = filters
                
            current_app.logger.info(f"Запрос к Метрике: {url} с параметрами {params}")
            
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                return data['data'][0]['metrics'][0]
            return 0
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Ошибка при получении данных из Метрики: {e}")
            if hasattr(e.response, 'text'):
                current_app.logger.error(f"Ответ сервера: {e.response.text}")
            return None
