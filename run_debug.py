from app import create_app, socketio
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)

app = create_app()
app.config['DEBUG'] = True

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False, port=5000)
