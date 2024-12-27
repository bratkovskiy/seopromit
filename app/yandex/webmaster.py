import requests
import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from flask import current_app

logger = logging.getLogger(__name__)

class YandexWebmasterAPI:
    BASE_URL = "https://api.webmaster.yandex.net/v4"
    
    def __init__(self, *, oauth_token: str, user_id: str):
        """
        Инициализирует API клиент для Яндекс.Вебмастера
        
        Args:
            oauth_token: OAuth токен для доступа к API
            user_id: ID пользователя в Яндекс.Вебмастере
        """
        self.user_id = user_id
        self.headers = {
            "Authorization": f"OAuth {oauth_token}",
            "Content-Type": "application/json"
        }
        logger.info(f"Инициализация YandexWebmasterAPI для user_id: {user_id}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Выполняет запрос к API с обработкой ошибок"""
        url = f"{self.BASE_URL}{endpoint}"
        logger.info(f"Отправка {method} запроса к: {url}")
        
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return None
    
    def get_host_id(self, host_url: str) -> Optional[str]:
        """Получает host_id по URL хоста"""
        logger.info(f"Получение host_id для {host_url}")
        
        # Нормализуем URL
        if host_url.startswith('https:') and not host_url.startswith('https://'):
            host_url = 'https://' + host_url[6:]
        if ':443' in host_url:
            host_url = host_url.replace(':443', '')
        logger.info(f"Нормализованный URL: {host_url}")
        
        # В рабочем скрипте host_id берется напрямую из таблицы
        # Здесь мы просто возвращаем последнюю часть URL как host_id
        if '/' in host_url:
            host_id = host_url.split('/')[-1]
            logger.info(f"Используем host_id: {host_id}")
            return host_id
            
        logger.error(f"Не удалось получить host_id для {host_url}")
        return None
    
    def get_keyword_position(self, host_id: str, query: str) -> Tuple[Optional[float], Optional[str]]:
        """Получает позицию ключевого слова"""
        logger.info(f"Получение позиции для запроса '{query}' на хосте {host_id}")
        
        # Определяем диапазон дат (последние 7 дней)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        
        url = f"/user/{self.user_id}/hosts/{host_id}/query-analytics/list"
        params = {
            "operation": "TEXT_CONTAINS",
            "limit": "500",
            "filters": {
                "text_filters": [
                    {
                        "text_indicator": "QUERY",
                        "operation": "TEXT_MATCH",
                        "value": query
                    }
                ]
            },
            "sort_by_date": {
                "date": start_date.strftime("%Y-%m-%d"),
                "statistic_field": "IMPRESSIONS",
                "by": "ASC"
            }
        }
        
        data = self._make_request("POST", url, json=params)
        if not data or 'text_indicator_to_statistics' not in data:
            logger.warning(f"Нет данных по запросу '{query}' в ответе API")
            return None, None
            
        positions = [stat for stat in data['text_indicator_to_statistics']
                    if stat['text_indicator']['value'] == query]
                    
        if not positions:
            logger.warning(f"Позиция для запроса '{query}' не найдена в данных API")
            return None, None
            
        position_data = positions[0]['statistics']
        position_entries = [entry for entry in position_data if entry['field'] == 'POSITION']
        
        if not position_entries:
            logger.warning(f"Нет данных о позициях для запроса '{query}'")
            return None, None
            
        # Берем последние 7 дней и считаем среднее
        position_entries_sorted = sorted(position_entries, key=lambda x: x['date'], reverse=True)[:7]
        positions_values = [entry['value'] for entry in position_entries_sorted]
        
        if not positions_values:
            logger.warning(f"Нет значений позиций для запроса '{query}'")
            return None, None
            
        position_avg = np.mean(positions_values)
        date_range = f"{start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}"
        
        logger.info(f"Средняя позиция для '{query}': {position_avg} за период {date_range}")
        return position_avg, date_range

    def validate_host(self, host_url: str) -> Tuple[bool, str]:
        """
        Проверяет доступность хоста в Вебмастере
        
        Args:
            host_url: URL хоста для проверки
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        logger.info(f"Проверка хоста {host_url}")
        
        # Используем тот же URL что и в рабочем скрипте
        endpoint = f"/user/{self.user_id}/hosts/{host_url}/query-analytics/list"
        
        # Используем те же параметры что и в рабочем скрипте
        params = {
            "operation": "TEXT_CONTAINS",
            "limit": "1"  # Нам нужен только один результат для проверки
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}{endpoint}",
                json=params,
                headers=self.headers
            )
            logger.info(f"Статус ответа: {response.status_code}")
            
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
            logger.error(error_msg)
            return False, error_msg

    def get_keywords_positions(self, host_url: str, keywords: List[str]) -> Dict[str, Tuple[Optional[float], Optional[str]]]:
        """
        Получает позиции для списка ключевых слов
        
        Args:
            host_url: URL хоста
            keywords: Список ключевых слов
            
        Returns:
            Dict[str, Tuple[float, str]]: Словарь {ключевое слово: (позиция, дата)}
        """
        logger.info(f"Получение позиций для {len(keywords)} ключевых слов на хосте {host_url}")
        
        # Сначала получаем host_id
        host_id = self.get_host_id(host_url)
        if not host_id:
            logger.error(f"Не удалось получить host_id для {host_url}")
            return {}
            
        # Получаем позиции для каждого ключевого слова
        results = {}
        for keyword in keywords:
            position, date = self.get_keyword_position(host_id, keyword)
            if position is not None:
                results[keyword] = (position, date)
            else:
                logger.warning(f"Не удалось получить позицию для '{keyword}'")
                
        return results
