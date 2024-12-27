from app import create_app, db
from app.models import Project

app = create_app()

def delete_project(project_id):
    with app.app_context():
        project = Project.query.get(project_id)
        if project:
            db.session.delete(project)
            db.session.commit()
            print(f"Project {project_id} deleted successfully")
        else:
            print(f"Project {project_id} not found")

if __name__ == '__main__':
    delete_project(1)  # Удаляем проект с ID 1
