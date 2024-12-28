import logging
from app import create_app

# Настройка логирования для отладки
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("=== Запуск приложения в режиме отладки ===")

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
