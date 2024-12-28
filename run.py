from app import create_app, socketio
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    socketio.run(app, debug=True)
