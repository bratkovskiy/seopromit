import requests
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class YandexWebmasterAPI:
    """Класс для работы с API Яндекс.Вебмастер"""
    
    BASE_URL = "https://api.webmaster.yandex.net/v4/user"
    
    def __init__(self, oauth_token, user_id):
        logger.info(f"Инициализация YandexWebmasterAPI для user_id: {user_id}")
        self.oauth_token = oauth_token
        self.user_id = user_id
        self.headers = {
            "Authorization": f"OAuth {oauth_token}",
            "Content-Type": "application/json"
        }
    
    def get_search_queries_position(self, host_id, query, date_from, date_to):
        """
        Получает позиции поискового запроса за указанный период
        
        :param host_id: ID хоста в Яндекс.Вебмастер
        :param query: Поисковый запрос
        :param date_from: Начальная дата в формате YYYY-MM-DD
        :param date_to: Конечная дата в формате YYYY-MM-DD
        :return: Словарь с данными о позициях или None в случае ошибки
        """
        logger.info(f"Запрос позиций для '{query}' с {date_from} по {date_to}")
        
        url = f"{self.BASE_URL}/{self.user_id}/hosts/{host_id}/search-queries/list"
        
        params = {
            "query_indicator": "TOTAL_SHOWS",
            "date_from": date_from,
            "date_to": date_to,
            "query_filter": query
        }
        
        try:
            logger.info(f"Отправка запроса к API: {url}")
            logger.debug(f"Параметры запроса: {json.dumps(params, indent=2)}")
            
            response = requests.get(url, headers=self.headers, params=params)
            logger.info(f"Получен ответ от API. Статус: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Ответ API: {json.dumps(data, indent=2)}")
            
            # Обработка ответа
            if 'queries' in data:
                logger.info(f"Успешно получены данные о позициях для '{query}'")
                return data
            else:
                logger.warning(f"Неожиданный формат ответа API для запроса '{query}'")
                logger.debug(f"Полученные данные: {json.dumps(data, indent=2)}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API Яндекс.Вебмастер: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при работе с API: {str(e)}")
            return None
