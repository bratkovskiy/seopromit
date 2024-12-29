from app import create_app, db
from app.models import Project, Keyword, KeywordPosition
from datetime import datetime

app = create_app()
with app.app_context():
    # Получаем все проекты
    projects = Project.query.all()
    print("\n=== Projects ===")
    for project in projects:
        print(f"\nProject ID: {project.id}")
        print(f"Project Name: {project.name}")
        
        # Получаем все ключевые слова проекта
        keywords = Keyword.query.filter_by(project_id=project.id).all()
        print(f"\nKeywords for project {project.id}:")
        if not keywords:
            print("No keywords found!")
        
        for keyword in keywords:
            print(f"\nKeyword ID: {keyword.id}")
            print(f"Keyword: {keyword.keyword}")
            
            # Получаем все позиции для ключевого слова
            positions = KeywordPosition.query.filter_by(keyword_id=keyword.id).order_by(
                KeywordPosition.check_date.desc()
            ).all()
            
            print(f"Positions for keyword {keyword.id}:")
            if not positions:
                print("No positions found!")
            
            for pos in positions:
                print(f"  Date: {pos.check_date}, Position: {pos.position}")
                print(f"  Period: {pos.data_date_start} - {pos.data_date_end}")
                print("  " + "-" * 30)
