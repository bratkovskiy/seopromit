from app import create_app, db

app = create_app()

def reset_db():
    with app.app_context():
        # Удаляем все таблицы
        db.drop_all()
        print('База данных очищена')
        
        # Создаем таблицы заново
        db.create_all()
        print('Таблицы созданы заново')

if __name__ == '__main__':
    reset_db()
