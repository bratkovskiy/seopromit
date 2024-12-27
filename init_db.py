from app import create_app, db
from app.models import User

app = create_app()

def init_db():
    with app.app_context():
        # Создаем все таблицы
        db.create_all()
        
        # Проверяем, существует ли уже админ
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            # Создаем администратора
            admin = User(
                username='admin',
                email='admin@example.com',
                role='admin'
            )
            admin.set_password('admin')  # Установите здесь свой пароль
            db.session.add(admin)
            db.session.commit()
            print('Администратор создан успешно!')
        else:
            print('Администратор уже существует')

if __name__ == '__main__':
    init_db()
