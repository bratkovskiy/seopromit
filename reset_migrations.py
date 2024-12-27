from app import create_app, db

app = create_app()

with app.app_context():
    # Удаляем таблицу alembic_version
    with db.engine.connect() as conn:
        conn.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
        print("Таблица alembic_version удалена")
