from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.main import bp
from app.main.forms import ProjectForm
from app.models import Project, Keyword, URL, KeywordPosition, URLTraffic, Region
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
    
    # Получаем список регионов для формы
    regions = Region.query.order_by(Region.name).all()
    
    return render_template('main/keywords.html', 
                         title='Keywords', 
                         project=project, 
                         keywords=project.keywords,
                         regions=regions,
                         KeywordPosition=KeywordPosition)  

@bp.route('/project/<int:id>/urls')
@login_required
def project_urls(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    return render_template('main/urls.html', title='URLs', project=project, urls=project.urls)

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

@bp.route('/project/<int:project_id>/keywords/add', methods=['POST'])
@login_required
def add_keyword(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    region_id = request.form.get('region_id')
    if not region_id:
        flash('Необходимо выбрать регион', 'error')
        return redirect(url_for('main.project_keywords', id=project_id))
    
    # Проверяем существование региона
    region = Region.query.get(region_id)
    if not region:
        flash('Выбранный регион не существует', 'error')
        return redirect(url_for('main.project_keywords', id=project_id))
    
    keywords_text = request.form.get('keywords', '').strip()
    if not keywords_text:
        flash('Список ключевых слов не может быть пустым', 'error')
        return redirect(url_for('main.project_keywords', id=project_id))
    
    # Разбиваем текст на отдельные ключевые слова
    keywords_list = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
    
    # Убираем дубликаты
    keywords_list = list(dict.fromkeys(keywords_list))
    
    # Добавляем каждое ключевое слово
    added_count = 0
    skipped_count = 0
    for keyword_text in keywords_list:
        # Проверяем, не существует ли уже такое ключевое слово для данного проекта и региона
        existing_keyword = Keyword.query.filter_by(
            project_id=project_id,
            region_id=region_id,
            keyword=keyword_text
        ).first()
        
        if existing_keyword:
            skipped_count += 1
            continue
            
        keyword = Keyword(
            keyword=keyword_text,
            project_id=project_id,
            region_id=region_id
        )
        db.session.add(keyword)
        added_count += 1
    
    db.session.commit()
    
    if added_count > 0:
        message = f'Добавлено {added_count} ключевых слов'
        if skipped_count > 0:
            message += f' (пропущено {skipped_count} дубликатов)'
        flash(message, 'success')
    else:
        if skipped_count > 0:
            flash(f'Все {skipped_count} ключевых слов уже существуют', 'warning')
        else:
            flash('Нет новых ключевых слов для добавления', 'warning')
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/keywords/<int:keyword_id>/delete', methods=['POST'])
@login_required
def delete_keyword(project_id, keyword_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    keyword = Keyword.query.get_or_404(keyword_id)
    if keyword.project_id != project_id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    db.session.delete(keyword)
    db.session.commit()
    flash('Ключевое слово удалено', 'success')
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/urls/add', methods=['POST'])
@login_required
def add_urls(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    urls_text = request.form.get('urls', '').strip()
    if not urls_text:
        flash('Список URLs не может быть пустым', 'error')
        return redirect(url_for('main.project_urls', id=project_id))
    
    # Разбиваем текст на отдельные URLs
    urls_list = [url.strip() for url in urls_text.split('\n') if url.strip()]
    
    # Убираем дубликаты и сохраняем информацию о количестве
    original_count = len(urls_list)
    unique_urls = list(dict.fromkeys(urls_list))
    duplicates_count = original_count - len(unique_urls)
    
    # Добавляем только уникальные URLs
    added_count = 0
    skipped_count = 0
    for url_text in unique_urls:
        # Проверяем, не существует ли уже такой URL для данного проекта
        existing_url = URL.query.filter_by(
            project_id=project_id,
            url=url_text
        ).first()
        
        if existing_url:
            skipped_count += 1
            continue
            
        url = URL(
            url=url_text,
            project_id=project_id
        )
        db.session.add(url)
        added_count += 1
    
    db.session.commit()
    
    # Формируем сообщение о результатах
    message_parts = []
    if added_count > 0:
        message_parts.append(f'Добавлено {added_count} новых URLs')
    if skipped_count > 0:
        message_parts.append(f'Пропущено {skipped_count} существующих URLs')
    if duplicates_count > 0:
        message_parts.append(f'Удалено {duplicates_count} повторяющихся URLs')
    
    if message_parts:
        flash('. '.join(message_parts), 'info')
    else:
        flash('Не добавлено ни одного URL', 'warning')
    
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:project_id>/url/<int:url_id>/delete', methods=['POST'])
@login_required
def delete_url(project_id, url_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    url = URL.query.get_or_404(url_id)
    if url.project_id != project_id:
        flash('URL не принадлежит данному проекту', 'error')
        return redirect(url_for('main.project_urls', id=project_id))
    
    db.session.delete(url)
    db.session.commit()
    flash('URL удален', 'success')
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:project_id>/urls/clear_all', methods=['POST'])
@login_required
def clear_all_urls(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Удаляем все URLs проекта
        URL.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        flash('Все URLs успешно удалены', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении URLs: {str(e)}', 'error')
    
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:id>/get_data')
@login_required
def get_project_data(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Здесь будет логика получения данных
        # TODO: Реализовать получение данных из Яндекс.Метрики и Яндекс.Вебмастера
        flash('Запрос на получение данных отправлен', 'success')
    except Exception as e:
        flash(f'Ошибка при получении данных: {str(e)}', 'error')
    
    return redirect(url_for('main.project', id=id))

@bp.route('/project/<int:project_id>/keywords/clear_all', methods=['POST'])
@login_required
def clear_all_keywords(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Удаляем все ключевые слова проекта
        Keyword.query.filter_by(project_id=project_id).delete()
        db.session.commit()
        flash('Все ключевые слова успешно удалены', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении ключевых слов: {str(e)}', 'error')
    
    return redirect(url_for('main.project_keywords', id=project_id))
