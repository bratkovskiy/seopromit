from app import create_app, db

app = create_app()
with app.app_context():
    # Удаляем все таблицы
    db.drop_all()
    print("База данных очищена")
