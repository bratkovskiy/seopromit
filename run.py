from app import create_app, socketio

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}

if __name__ == '__main__':
    socketio.run(app, debug=True)
