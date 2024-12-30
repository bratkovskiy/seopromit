import os
import sys

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Project, URL, URLTraffic
from datetime import datetime, timedelta
import random

app = create_app()

def generate_traffic_data(project_id, num_dates=10):
    with app.app_context():
        project = Project.query.get(project_id)
        if not project:
            print(f"Project with id {project_id} not found")
            return

        # Получаем все URLs проекта
        urls = URL.query.filter_by(project_id=project_id).all()
        if not urls:
            print(f"No URLs found for project {project_id}")
            return

        # Генерируем даты
        end_date = datetime.now()
        dates = [(end_date - timedelta(days=i)).date() for i in range(num_dates)]
        dates.reverse()  # Сортируем даты по возрастанию

        # Для каждого URL генерируем данные по трафику
        for url in urls:
            prev_traffic = None
            for date in dates:
                # Генерируем случайное значение трафика
                if prev_traffic is None:
                    traffic_value = random.randint(50, 1000)
                else:
                    # Генерируем значение в пределах ±30% от предыдущего
                    min_val = int(prev_traffic * 0.7)
                    max_val = int(prev_traffic * 1.3)
                    traffic_value = random.randint(min_val, max_val)

                # Создаем запись о трафике
                traffic_data = URLTraffic(
                    url_id=url.id,
                    check_date=date,
                    visits=traffic_value
                )
                db.session.add(traffic_data)
                prev_traffic = traffic_value

        try:
            db.session.commit()
            print(f"Successfully generated traffic data for project {project_id}")
        except Exception as e:
            db.session.rollback()
            print(f"Error generating traffic data: {str(e)}")

if __name__ == "__main__":
    generate_traffic_data(1)  # Генерируем данные для проекта с id=1
