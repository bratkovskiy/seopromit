from app import create_app, db
from app.models import URL, Project, Keyword

def create_default_urls():
    app = create_app()
    with app.app_context():
        # Получаем все проекты
        projects = Project.query.all()
        
        for project in projects:
            print(f"\nProcessing project: {project.name}")
            
            # Проверяем, есть ли URL у проекта
            urls = URL.query.filter_by(project_id=project.id).all()
            if not urls and project.url:  # Если нет URL, но есть основной URL проекта
                # Создаем URL из основного URL проекта
                new_url = URL(
                    url=project.url,
                    project_id=project.id
                )
                db.session.add(new_url)
                db.session.commit()
                print(f"Created default URL: {new_url.url}")
                
                # Привязываем все ключевые слова к этому URL
                keywords = Keyword.query.filter_by(project_id=project.id).all()
                for keyword in keywords:
                    keyword.url_id = new_url.id
                
                db.session.commit()
                print(f"Linked {len(keywords)} keywords to the default URL")

if __name__ == '__main__':
    create_default_urls()
