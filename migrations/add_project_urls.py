from app import create_app, db
from app.models import Project, URL, Keyword

def add_project_urls():
    app = create_app()
    with app.app_context():
        # Получаем проект без URL
        project = Project.query.filter_by(name="Новый проектик").first()
        if project:
            print(f"Found project: {project.name}")
            
            # Создаем URL для проекта
            project.url = "https://example.com"  # Замените на реальный URL
            
            # Создаем запись в таблице URL
            new_url = URL(
                url=project.url,
                project_id=project.id
            )
            db.session.add(new_url)
            db.session.commit()
            print(f"Created URL: {new_url.url}")
            
            # Привязываем все ключевые слова к этому URL
            keywords = Keyword.query.filter_by(project_id=project.id).all()
            for keyword in keywords:
                keyword.url_id = new_url.id
            
            db.session.commit()
            print(f"Linked {len(keywords)} keywords to the URL")

if __name__ == '__main__':
    add_project_urls()
