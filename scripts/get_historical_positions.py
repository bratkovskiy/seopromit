import sys
import os
import logging
from datetime import datetime, timedelta
import numpy as np
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time


# Добавляем путь к корневой директории проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Project, Keyword, KeywordPosition
from app.yandex.webmaster import YandexWebmasterAPI
from config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('historical_positions.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_historical_positions(api: YandexWebmasterAPI, host_id: str, query: str, periods_count: int) -> list:
    """
    Получает исторические данные о позициях ключевого слова за несколько периодов
    """
    logger.info(f"Получение исторических позиций для запроса '{query}' на хосте {host_id} за {periods_count} периодов")
    
    results = []
    for period in range(periods_count):
        # Вычисляем даты для текущего периода
        end_date = datetime.now().date() - timedelta(days=period * 7)
        start_date = end_date - timedelta(days=6)
        
        url = f"/user/{api.user_id}/hosts/{host_id}/query-analytics/list"
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
        
        data = api._make_request("POST", url, json=params)
        if not data or 'text_indicator_to_statistics' not in data:
            logger.warning(f"Нет данных по запросу '{query}' за период {start_date} - {end_date}")
            continue
            
        positions = [stat for stat in data['text_indicator_to_statistics']
                    if stat['text_indicator']['value'] == query]
                    
        if not positions:
            logger.warning(f"Позиция для запроса '{query}' не найдена за период {start_date} - {end_date}")
            continue
            
        position_data = positions[0]['statistics']
        position_entries = [entry for entry in position_data if entry['field'] == 'POSITION']
        
        if not position_entries:
            logger.warning(f"Нет данных о позициях для запроса '{query}' за период {start_date} - {end_date}")
            continue
            
        # Берем данные за текущий период и считаем среднее
        positions_values = [entry['value'] for entry in position_entries]
        
        if positions_values:
            position_avg = np.mean(positions_values)
            date_range = f"{start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}"
            results.append((position_avg, date_range))
            logger.info(f"Средняя позиция для '{query}': {position_avg} за период {date_range}")
            
    return results

def main():
    parser = argparse.ArgumentParser(description='Получение исторических данных о позициях ключевых слов')
    parser.add_argument('project_id', type=int, help='ID проекта')
    parser.add_argument('periods_count', type=int, help='Количество периодов (1 период = 7 дней)')
    args = parser.parse_args()

    # Создаем подключение к базе данных
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Получаем проект
        project = session.query(Project).get(args.project_id)
        if not project:
            logger.error(f"Проект с ID {args.project_id} не найден")
            return

        # Создаем клиент API
        api = YandexWebmasterAPI(
            oauth_token=project.yandex_webmaster_token,
            user_id=project.yandex_webmaster_user_id
        )

        # Получаем все ключевые слова проекта
        keywords = session.query(Keyword).filter_by(project_id=args.project_id).all()
        if not keywords:
            logger.error("У проекта нет ключевых слов для обновления")
            return

        success_count = 0
        error_count = 0
        
        # Обрабатываем каждое ключевое слово
        for keyword in keywords:
            try:
                historical_data = get_historical_positions(
                    api,
                    project.yandex_webmaster_host,
                    keyword.keyword,
                    args.periods_count
                )

                if historical_data:
                    for position, date_range in historical_data:
                        try:
                            # Создаем новую запись в таблице KeywordPosition
                            keyword_position = KeywordPosition(
                                keyword_id=keyword.id,
                                position=position,
                                check_date=datetime.utcnow()
                            )
                            
                            # Парсим даты из строки формата "dd.mm - dd.mm"
                            if date_range:
                                start_date_str, end_date_str = date_range.split(' - ')
                                current_year = datetime.now().year
                                
                                # Преобразуем строки дат в объекты datetime
                                start_date = datetime.strptime(f"{start_date_str}.{current_year}", '%d.%m.%Y')
                                end_date = datetime.strptime(f"{end_date_str}.{current_year}", '%d.%m.%Y')
                                
                                # Устанавливаем даты
                                keyword_position.data_date_start = start_date
                                keyword_position.data_date_end = end_date
                                
                            session.add(keyword_position)
                            success_count += 1
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении исторических данных для '{keyword.keyword}': {e}")
                            error_count += 1

            except Exception as e:
                logger.error(f"Ошибка при получении исторических данных для '{keyword.keyword}': {e}")
                error_count += 1

        if success_count > 0:
            session.commit()
            logger.info(f"Успешно получены исторические данные: {success_count} записей (ошибок: {error_count})")
        else:
            session.rollback()
            logger.error("Не удалось сохранить исторические данные")

    except Exception as e:
        session.rollback()
        logger.error(f"Произошла ошибка: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    main()
