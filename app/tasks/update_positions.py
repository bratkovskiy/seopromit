import logging
import os
from datetime import datetime, timedelta
import requests
import backoff
from app import db
from app.models import Project, Keyword, KeywordPosition
from app.yandex import YandexWebmasterAPI
from app.email import send_email

# Настройка логирования в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
def fetch_position_data(host, query, token, user_id):
    """Получает позицию для ключевого слова из API Яндекс.Вебмастер."""
    try:
        api = YandexWebmasterAPI(
            oauth_token=token,
            user_id=user_id
        )
        
        # Получаем даты для запроса (последние 7 дней)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        logger.info(f"Запрашиваем позиции для '{query}' с {start_date} по {end_date}")
        
        # Получаем данные из API
        positions = api.get_keywords_positions(
            host_url=host,
            keywords=[query]
        )
        
        if positions and query in positions:
            position, date_range = positions[query]
            if position is not None:
                logger.info(f"Средняя позиция для '{query}': {position:.2f}")
                return position, date_range
        
        logger.warning(f"Нет данных о позициях для '{query}'")
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении позиции для '{query}': {str(e)}")
        return None

def update_project_positions(project_id):
    """Обновляет позиции для всех ключевых слов проекта."""
    pid_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', f'update_positions_{project_id}.pid')
    
    try:
        # Создаем PID файл
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
            
        logger.info(f"Начало обновления позиций для проекта {project_id}")
        
        # Получаем проект
        project = Project.query.get(project_id)
        if not project:
            logger.error(f"Проект {project_id} не найден")
            return
            
        logger.info(f"Проект {project.name} найден")

        # Получаем все ключевые слова проекта
        keywords = project.keywords.all()
        if not keywords:
            logger.warning(f"У проекта {project_id} нет ключевых слов для обновления")
            return
            
        logger.info(f"Найдено {len(keywords)} ключевых слов")

        # Получаем позиции для всех ключевых слов
        logger.info("Запрашиваем позиции из API...")
        positions = {}
        for keyword in keywords:
            logger.info(f"Получаем позицию для '{keyword.keyword}'...")
            result = fetch_position_data(
                project.yandex_webmaster_host,
                keyword.keyword,
                project.yandex_webmaster_token,
                project.yandex_webmaster_user_id
            )
            if result:
                position, date_range = result
                positions[keyword.keyword] = (position, date_range)
                logger.info(f"Позиция для '{keyword.keyword}': {position}")
            else:
                logger.warning(f"Не удалось получить позицию для '{keyword.keyword}'")
        
        if not positions:
            logger.warning("API вернул пустой словарь позиций")
            send_email(
                subject=f"Нет данных по позициям для проекта {project.name}",
                recipient=project.user.email,
                text_body=f"Не удалось получить позиции ни для одного ключевого слова в проекте {project.name}"
            )
            return

        # Обновляем позиции в базе данных
        success_count = 0
        error_count = 0
        
        logger.info(f"Начинаем обновление {len(positions)} позиций в базе данных")
        
        for keyword_text, (position, date_range) in positions.items():
            if position is not None:
                keyword = Keyword.query.filter_by(
                    project_id=project_id,
                    keyword=keyword_text
                ).first()
                
                if keyword:
                    try:
                        # Создаем новую запись в таблице KeywordPosition
                        keyword_position = KeywordPosition(
                            keyword_id=keyword.id,
                            position=position,
                            check_date=datetime.utcnow()
                        )
                        
                        # Парсим даты из строки формата "dd.mm - dd.mm"
                        if date_range:
                            try:
                                start_str, end_str = date_range.split(' - ')
                                current_year = datetime.now().year
                                
                                # Преобразуем строки в объекты datetime
                                start_date = datetime.strptime(f"{start_str}.{current_year}", "%d.%m.%Y")
                                end_date = datetime.strptime(f"{end_str}.{current_year}", "%d.%m.%Y")
                                
                                keyword_position.data_date_start = start_date
                                keyword_position.data_date_end = end_date
                            except Exception as e:
                                logger.warning(f"Ошибка при парсинге дат '{date_range}': {e}")
                        
                        db.session.add(keyword_position)
                        keyword.last_webmaster_update = datetime.utcnow()
                        success_count += 1
                        logger.info(f"Успешно обновлена позиция для '{keyword_text}': {position}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Ошибка при обновлении позиции для '{keyword_text}': {e}")

        if success_count > 0:
            try:
                db.session.commit()
                logger.info(f"Успешно сохранено {success_count} позиций в базе данных")
                
                # Отправляем email об успешном обновлении
                message = f"Успешно обновлено {success_count} из {len(keywords)} ключевых слов"
                if error_count > 0:
                    message += f" (ошибок: {error_count})"
                    
                send_email(
                    subject=f"Позиции обновлены для проекта {project.name}",
                    recipient=project.user.email,
                    text_body=message
                )
            except Exception as e:
                logger.error(f"Ошибка при сохранении в базу данных: {e}")
                db.session.rollback()
                raise
        else:
            logger.warning("Нет успешно обновленных позиций")
            db.session.rollback()

    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении позиций: {e}")
        try:
            send_email(
                subject=f"Ошибка обновления позиций для проекта {project.name}",
                recipient=project.user.email,
                text_body=f"Произошла ошибка при обновлении позиций: {str(e)}"
            )
        except:
            logger.error("Не удалось отправить email об ошибке")
        raise
    finally:
        # Удаляем PID файл в любом случае
        try:
            os.remove(pid_file)
        except OSError:
            pass
