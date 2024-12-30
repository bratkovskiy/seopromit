from app import create_app, db
from app.models import Keyword, URL, Project

def migrate_keywords_to_urls():
    app = create_app()
    with app.app_context():
        # Получаем все проекты
        projects = Project.query.all()
        
        for project in projects:
            print(f"\nProcessing project: {project.name}")
            
            # Получаем все URL проекта
            urls = URL.query.filter_by(project_id=project.id).all()
            print(f"Found {len(urls)} URLs")
            
            # Получаем все ключевые слова проекта
            keywords = Keyword.query.filter_by(project_id=project.id).all()
            print(f"Found {len(keywords)} keywords")
            
            # Для каждого ключевого слова находим соответствующий URL
            for keyword in keywords:
                if keyword.url_id is None:  # Если URL еще не установлен
                    # Ищем URL с тем же project_id
                    if urls:
                        # Временно привязываем к первому URL проекта
                        keyword.url_id = urls[0].id
                        print(f"Linked keyword '{keyword.keyword}' to URL '{urls[0].url}'")
            
            # Сохраняем изменения
            db.session.commit()
            print("Changes committed")

if __name__ == '__main__':
    migrate_keywords_to_urls()
