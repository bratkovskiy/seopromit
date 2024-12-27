from app import create_app, db
from app.models import Project

app = create_app()
with app.app_context():
    projects = Project.query.all()
    print("\nПроекты в базе данных:")
    for p in projects:
        print(f"ID: {p.id}")
        print(f"Name: {p.name}")
        print(f"Host: {p.yandex_webmaster_host}")
        print(f"Host ID: {p.yandex_webmaster_host_id}")
        print("---")
