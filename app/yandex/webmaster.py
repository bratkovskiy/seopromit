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
            if response.status_code != 200:
                error_msg = f"Ошибка при запросе к API: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error_message' in error_data:
                        error_msg += f" - {error_data['error_message']}"
                    elif 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                return None
                
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return None
    
    def get_keywords_positions(self, host_url: str, keywords: List[str]) -> Dict[str, Tuple[Optional[float], Optional[str]]]:
        """
        Получает позиции для списка ключевых слов
        
        Args:
            host_url: URL хоста (используется как host_id)
            keywords: Список ключевых слов
            
        Returns:
            Dict[str, Tuple[float, str]]: Словарь {ключевое слово: (позиция, дата)}
        """
        logger.info(f"Получение позиций для {len(keywords)} ключевых слов на хосте {host_url}")
        
        # Используем host_url как host_id
        host_id = host_url
        
        # Получаем позиции для каждого ключевого слова
        results = {}
        for keyword in keywords:
            try:
                position, date = self.get_keyword_position(host_id, keyword)
                if position is not None:
                    results[keyword] = (position, date)
                else:
                    logger.warning(f"Не удалось получить позицию для '{keyword}'")
            except Exception as e:
                logger.error(f"Ошибка при получении позиции для '{keyword}': {e}")
                
        return results

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
        
        # Логируем запрос для отладки
        logger.info(f"API запрос: POST {url}")
        logger.info(f"Параметры: {params}")
        
        data = self._make_request("POST", url, json=params)
        if not data or 'text_indicator_to_statistics' not in data:
            logger.warning(f"Нет данных по запросу '{query}' в ответе API")
            logger.warning(f"Ответ API: {data}")
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
        logger.info(f"Начало валидации хоста Вебмастера: {host_url}")
        
        try:
            # Делаем прямой запрос к API для проверки хоста
            endpoint = f'/user/{self.user_id}/hosts/{host_url}'
            logger.info(f"Отправка GET запроса к {self.BASE_URL}{endpoint}")
            
            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=self.headers
            )
            
            logger.info(f"Получен ответ от API Вебмастера: статус {response.status_code}")
            logger.info(f"Тело ответа: {response.text[:200]}...")  # Логируем первые 200 символов ответа
            
            if response.status_code == 200:
                logger.info(f"Хост {host_url} успешно валидирован")
                return True, "Хост успешно подключен в Яндекс.Вебмастере"
            elif response.status_code == 404:
                logger.error(f"Хост {host_url} не найден в Яндекс.Вебмастере")
                return False, "Указанный хост не найден в Яндекс.Вебмастере"
            else:
                error_msg = f"Ошибка при запросе к API: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error_message' in error_data:
                        error_msg += f" - {error_data['error_message']}"
                    elif 'message' in error_data:
                        error_msg += f" - {error_data['message']}"
                except:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f'Ошибка при проверке хоста в Вебмастере: {str(e)}'
            logger.error(error_msg)
            return False, error_msg
