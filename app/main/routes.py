from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.main import bp
from app.main.forms import ProjectForm
from app.models import Project, Keyword, URL, KeywordPosition, URLTraffic
from app.yandex import YandexMetrikaAPI, YandexWebmasterAPI
from datetime import datetime

@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('main/dashboard.html', title='Панель управления', projects=projects)

@bp.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    form = ProjectForm()
    if form.validate_on_submit():
        # Проверяем, что оба сервиса были валидированы
        if form.metrika_validated.data != 'true' or form.webmaster_validated.data != 'true':
            flash('Необходимо проверить подключение к сервисам Яндекса', 'error')
            return redirect(url_for('main.new_project'))
            
        project = Project(
            name=form.name.data,
            yandex_metrika_counter=form.yandex_metrika_counter.data,
            yandex_metrika_token=form.yandex_metrika_token.data,
            yandex_webmaster_host=form.yandex_webmaster_host.data,
            yandex_webmaster_token=form.yandex_webmaster_token.data,
            yandex_webmaster_user_id=form.yandex_webmaster_user_id.data,
            user_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        flash('Проект успешно создан!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('main/new_project.html', title='Новый проект', form=form)

@bp.route('/project/<int:id>')
@login_required
def project(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    return render_template('main/project.html', title=project.name, project=project)

@bp.route('/project/<int:id>/keywords')
@login_required
def project_keywords(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    keywords = project.keywords.all()
    return render_template('main/keywords.html', title='Keywords', project=project, keywords=keywords)

@bp.route('/project/<int:id>/urls')
@login_required
def project_urls(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    urls = project.urls.all()
    return render_template('main/urls.html', title='URLs', project=project, urls=urls)

@bp.route('/project/<int:id>/delete', methods=['POST'])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/validate_metrika', methods=['POST'])
@login_required
def validate_metrika():
    data = request.get_json()
    counter = data.get('counter')
    token = data.get('token')
    
    if not counter or not token:
        return jsonify({
            'success': False,
            'message': 'Необходимо указать ID счетчика и токен'
        })
    
    api = YandexMetrikaAPI(token)
    success, message = api.validate_counter(counter)
    
    return jsonify({
        'success': success,
        'message': message
    })

@bp.route('/validate_webmaster', methods=['POST'])
@login_required
def validate_webmaster():
    print("=== Начало валидации вебмастера ===")
    data = request.get_json()
    print(f"Полученные данные: {data}")
    
    host = data.get('host')
    token = data.get('token')
    user_id = data.get('user_id')
    
    print(f"Host: {host}")
    print(f"Token: {token[:15]}..." if token else "Token: None")
    print(f"User ID: {user_id}")
    
    if not host or not token or not user_id:
        error_msg = 'Необходимо указать хост, токен и user_id'
        print(f"Ошибка: {error_msg}")
        return jsonify({
            'success': False,
            'message': error_msg
        })
    
    api = YandexWebmasterAPI(token)
    print("Вызываем метод validate_host")
    success, message = api.validate_host(host, user_id)
    print(f"Результат: success={success}, message={message}")
    
    response = {
        'success': success,
        'message': message
    }
    print(f"Отправляем ответ: {response}")
    return jsonify(response)
