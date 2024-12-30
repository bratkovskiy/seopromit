from flask import render_template, flash, redirect, url_for, request, jsonify, current_app, session
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from app import db, socketio, csrf
from app.main import bp
from app.main.forms import ProjectForm, URLForm, KeywordForm
from app.models import User, Project, Keyword, KeywordPosition, URL, URLTraffic, Region
from app.yandex import YandexMetrikaAPI, YandexWebmasterAPI
from datetime import datetime, timedelta
import logging
import threading
import time
from urllib.parse import urlparse
import io
import xlsxwriter
from flask import send_file
import builtins
from app.tasks.update_positions import update_project_positions  # Добавляем импорт
import os

logger = logging.getLogger(__name__)

@bp.context_processor
def inject_models():
    return {
        'User': User,
        'Project': Project,
        'Region': Region,
        'Keyword': Keyword,
        'KeywordPosition': KeywordPosition,
        'URL': URL,
        'URLTraffic': URLTraffic
    }

@login_required
@bp.route('/')
@bp.route('/dashboard')
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('main/dashboard.html', title='Панель управления', projects=projects)

@login_required
@bp.route('/project/new', methods=['GET', 'POST'])
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
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('main.index'))
        
    # Проверяем наличие региона по умолчанию
    default_region = Region.query.filter_by(code=213).first()  # 213 - код Москвы
    if not default_region:
        default_region = Region(name='Москва', code=213)
        db.session.add(default_region)
        db.session.commit()
        current_app.logger.info('Создан регион по умолчанию (Москва)')
    
    # Проверяем и обновляем регион для ключевых слов
    for keyword in project.keywords:
        if not keyword.region_id:
            keyword.region_id = default_region.id
    db.session.commit()
        
    return render_template('main/project.html', project=project)

@bp.route('/project/<int:id>/keywords', methods=['GET', 'POST'])
@login_required
def project_keywords(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = KeywordForm()
    regions = Region.query.order_by(Region.name).all()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            region_id = request.form.get('region_id')
            if not region_id:
                flash('Выберите регион', 'error')
                return render_template('main/keywords.html', 
                                    title='Ключевые слова',
                                    project=project,
                                    regions=regions,
                                    form=form)
            
            keywords_text = form.keywords.data.strip()
            if not keywords_text:
                flash('Введите ключевые слова', 'error')
                return render_template('main/keywords.html', 
                                    title='Ключевые слова',
                                    project=project,
                                    regions=regions,
                                    form=form)
            
            # Разбиваем текст на отдельные ключевые слова
            keywords_list = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
            added_count = 0
            exists_count = 0
            error_count = 0
            
            for keyword_text in keywords_list:
                # Проверяем, не существует ли уже такое ключевое слово для данного проекта и региона
                existing_keyword = Keyword.query.filter_by(
                    project_id=id,
                    keyword=keyword_text,
                    region_id=region_id
                ).first()
                
                if existing_keyword:
                    exists_count += 1
                    continue
                
                try:
                    keyword = Keyword(
                        keyword=keyword_text,
                        project_id=id,
                        region_id=region_id
                    )
                    db.session.add(keyword)
                    db.session.commit()
                    added_count += 1
                except Exception as e:
                    db.session.rollback()
                    error_count += 1
                    current_app.logger.error(f"Error adding keyword '{keyword_text}' to project {id}: {str(e)}")
            
            if added_count > 0:
                flash(f'Добавлено {added_count} ключевых слов', 'success')
            if exists_count > 0:
                flash(f'{exists_count} ключевых слов уже существуют', 'warning')
            if error_count > 0:
                flash(f'Не удалось добавить {error_count} ключевых слов', 'error')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Ошибка в поле {getattr(form, field).label.text}: {error}', 'error')
    
    return render_template('main/keywords.html', 
                         title='Ключевые слова',
                         project=project,
                         regions=regions,
                         form=form)

@bp.route('/project/<int:id>/keywords/table')
@login_required
def get_keywords_table(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Получаем ключевые слова проекта
    keywords = project.keywords.order_by(Keyword.keyword.asc()).all()
    
    # Рендерим только таблицу с ключевыми словами
    return render_template('main/_keywords_table.html', 
                         project=project, 
                         keywords=keywords)

@bp.route('/project/<int:id>/urls')
@login_required
def project_urls(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    form = URLForm()
    return render_template('main/urls.html', title='URLs', project=project, urls=project.urls, form=form)

@bp.route('/project/<int:project_id>/urls/add', methods=['POST'])
@login_required
def add_urls(project_id):
    form = URLForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        urls_text = form.urls.data.strip()
        if not urls_text:
            flash('Введите URLs', 'error')
            return redirect(url_for('main.project_urls', id=project_id))
        
        # Разбиваем текст на отдельные URLs
        urls_list = [url.strip() for url in urls_text.split('\n') if url.strip()]
        added_count = 0
        exists_count = 0
        error_count = 0
        
        for url_text in urls_list:
            # Проверяем, не существует ли уже такой URL
            existing_url = URL.query.filter_by(
                project_id=project_id,
                url=url_text
            ).first()
            
            if existing_url:
                exists_count += 1
                continue
            
            try:
                url = URL(url=url_text, project_id=project_id)
                db.session.add(url)
                db.session.commit()
                added_count += 1
            except Exception as e:
                db.session.rollback()
                error_count += 1
                current_app.logger.error(f"Error adding URL '{url_text}' to project {project_id}: {str(e)}")
        
        if added_count > 0:
            flash(f'Добавлено {added_count} URLs', 'success')
        if exists_count > 0:
            flash(f'{exists_count} URLs уже существуют', 'warning')
        if error_count > 0:
            flash(f'Не удалось добавить {error_count} URLs', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Ошибка в поле {getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:project_id>/url/<int:url_id>/delete', methods=['POST'])
@login_required
def delete_url(project_id, url_id):
    form = URLForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        url = URL.query.get_or_404(url_id)
        if url.project_id != project_id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        try:
            db.session.delete(url)
            db.session.commit()
            flash('URL успешно удален.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при удалении URL: {str(e)}', 'error')
    
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:project_id>/urls/clear', methods=['POST'])
@login_required
def clear_all_urls(project_id):
    form = URLForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        try:
            URL.query.filter_by(project_id=project_id).delete()
            db.session.commit()
            flash('Все URLs успешно удалены.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при удалении URLs: {str(e)}', 'error')
    
    return redirect(url_for('main.project_urls', id=project_id))

@bp.route('/project/<int:id>/delete', methods=['POST'])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Удаляем все связанные данные
        # URLs и их трафик будут удалены автоматически благодаря cascade='all, delete-orphan'
        # Ключевые слова и их позиции тоже будут удалены автоматически
        db.session.delete(project)
        db.session.commit()
        flash('Проект успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении проекта: {str(e)}', 'error')
        current_app.logger.error(f"Error deleting project {id}: {str(e)}")
    
    return redirect(url_for('main.dashboard'))

@bp.route('/validate_metrika', methods=['POST'])
@login_required
@csrf.exempt
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
@csrf.exempt
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
    
    api = YandexWebmasterAPI(oauth_token=token, user_id=user_id)
    print("Вызываем метод validate_host")
    success, message = api.validate_host(host)
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
    form = KeywordForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        region_id = request.form.get('region_id')
        if not region_id:
            flash('Выберите регион', 'error')
            return redirect(url_for('main.project_keywords', id=project_id))
        
        keyword_text = form.keywords.data
        
        # Проверяем, не существует ли уже такое ключевое слово для данного проекта
        existing_keyword = Keyword.query.filter_by(
            project_id=project_id,
            keyword=keyword_text,
            region_id=region_id
        ).first()
        
        if existing_keyword:
            flash('Такое ключевое слово уже существует для выбранного региона', 'error')
        else:
            keyword = Keyword(
                keyword=keyword_text,
                project_id=project_id,
                region_id=region_id
            )
            db.session.add(keyword)
            db.session.commit()
            flash('Ключевое слово добавлено', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Ошибка в поле {getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/keyword/<int:keyword_id>/delete', methods=['POST'])
@login_required
def delete_keyword(project_id, keyword_id):
    form = KeywordForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        keyword = Keyword.query.get_or_404(keyword_id)
        if keyword.project_id != project_id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        try:
            db.session.delete(keyword)
            db.session.commit()
            flash('Ключевое слово успешно удалено', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при удалении ключевого слова: {str(e)}', 'error')
            current_app.logger.error(f"Error deleting keyword {keyword_id} from project {project_id}: {str(e)}")
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/keywords/clear', methods=['POST'])
@login_required
def clear_all_keywords(project_id):
    form = KeywordForm()
    if form.validate_on_submit():
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.dashboard'))
        
        try:
            Keyword.query.filter_by(project_id=project_id).delete()
            db.session.commit()
            flash('Все ключевые слова успешно удалены', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при удалении ключевых слов: {str(e)}', 'error')
            current_app.logger.error(f"Error clearing all keywords for project {project_id}: {str(e)}")
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/get_data', methods=['POST'])
@login_required
def get_project_data(project_id):
    try:
        current_app.logger.info("="*50)
        current_app.logger.info(f"Starting data update for project {project_id}")
        current_app.logger.info(f"Request method: {request.method}")
        current_app.logger.info(f"Request headers: {dict(request.headers)}")
        
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Эмулируем процесс обновления с отправкой прогресса
        for progress in range(0, 101, 20):
            socketio.emit('update_progress', {'progress': progress})
            time.sleep(1)  # Имитация длительной операции
        
        # После завершения обновления
        socketio.emit('update_complete', {'message': 'Данные успешно обновлены'})
        return jsonify({'status': 'success', 'message': 'Данные успешно обновлены'})

    except Exception as e:
        current_app.logger.error(f"Error in get_project_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/project/<int:project_id>/positions/report', methods=['GET'])
@login_required
def project_positions_report(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Get all positions with related data
    positions = db.session.query(
        KeywordPosition.position,
        KeywordPosition.check_date,
        KeywordPosition.data_date_start,
        KeywordPosition.data_date_end,
        Keyword.keyword
    ).join(
        Keyword, KeywordPosition.keyword_id == Keyword.id
    ).filter(
        Keyword.project_id == project_id
    ).order_by(
        KeywordPosition.check_date.desc()
    ).all()

    # Get unique keywords
    keywords = sorted(list({pos.keyword for pos in positions}))

    # Get all check dates without limit
    check_dates = sorted(list({pos.check_date.strftime('%Y-%m-%d') for pos in positions}), reverse=True)

    # Prepare data for template
    positions_data = {}
    for keyword in keywords:
        positions_data[keyword] = {}
        for date in check_dates:
            positions_data[keyword][date] = {
                'position': None,
                'data_period': None
            }

    # Fill in the data
    for pos in positions:
        check_date = pos.check_date.strftime('%Y-%m-%d')
        positions_data[pos.keyword][check_date] = {
            'position': pos.position,
            'data_period': f"{pos.data_date_start.strftime('%Y-%m-%d')} - {pos.data_date_end.strftime('%Y-%m-%d')}"
        }

    # Calculate changes and statistics
    changes_data = {
        'total_keywords': len(keywords),
        'improved': 0,
        'worsened': 0,
        'unchanged': 0,
        'top10': 0,
        'top25': 0,
        'top100': 0,
        'over100': 0
    }

    position_changes = []

    # Для каждого ключевого слова
    for keyword in keywords:
        # Получаем все позиции для ключевого слова с датами
        keyword_positions = [(date, positions_data[keyword][date]['position']) 
                           for date in check_dates 
                           if positions_data[keyword][date]['position'] is not None]
        
        if len(keyword_positions) >= 2:
            # Сортируем по дате (уже отсортировано в обратном порядке)
            current_date, current_pos = keyword_positions[0]  # Самая новая дата
            previous_date, previous_pos = keyword_positions[1]  # Предыдущая дата
            
            change = previous_pos - current_pos  # Положительное значение = улучшение

            # Считаем изменения
            if change > 0:
                changes_data['improved'] += 1
            elif change < 0:
                changes_data['worsened'] += 1
            else:
                changes_data['unchanged'] += 1

            # Считаем распределение по текущей позиции
            if current_pos <= 10:
                changes_data['top10'] += 1
            elif current_pos <= 25:
                changes_data['top25'] += 1
            elif current_pos <= 100:
                changes_data['top100'] += 1
            else:
                changes_data['over100'] += 1

            # Добавляем в список изменений
            position_changes.append({
                'keyword': keyword,
                'current_position': current_pos,
                'previous_position': previous_pos,
                'change': change
            })

    # Сортируем и получаем наибольшие изменения
    biggest_improvements = sorted(
        [x for x in position_changes if x['change'] > 0],
        key=lambda x: x['change'],
        reverse=True
    )[:10]

    biggest_drops = sorted(
        [x for x in position_changes if x['change'] < 0],
        key=lambda x: abs(x['change']),
        reverse=True
    )[:10]

    # Calculate average positions for chart
    avg_positions = []
    for date in check_dates:
        positions_list = [
            dates[date]['position']
            for dates in positions_data.values()
            if dates[date]['position'] is not None
        ]
        if positions_list:
            avg = round(sum(positions_list) / len(positions_list), 1)
            avg_positions.append({
                'x': date,
                'y': avg
            })
    
    print("Debug - avg_positions:", avg_positions)  # Отладочный вывод

    # Get all check dates without limit
    check_dates = sorted(list({pos.check_date.strftime('%Y-%m-%d') for pos in positions}), reverse=True)

    return render_template('main/positions_report.html',
                         project=project,
                         positions_data=positions_data,
                         check_dates=check_dates,
                         avg_positions=avg_positions,
                         changes_data=changes_data,
                         biggest_improvements=biggest_improvements,
                         biggest_drops=biggest_drops)

@bp.route('/project/<int:project_id>/positions/table')
@login_required
def project_positions_table(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Get all keyword positions for the project
    positions = (KeywordPosition.query
                .join(Keyword)
                .filter(Keyword.project_id == project_id)
                .order_by(KeywordPosition.check_date.desc())
                .all())

    # Group positions by keyword and date
    positions_by_keyword = {}
    for pos in positions:
        keyword = pos.keyword.keyword
        if keyword not in positions_by_keyword:
            positions_by_keyword[keyword] = []
        positions_by_keyword[keyword].append({
            'date': pos.check_date.strftime('%Y-%m-%d'),
            'position': pos.position
        })

    # Sort positions for each keyword by date
    for keyword in positions_by_keyword:
        positions_by_keyword[keyword].sort(key=lambda x: x['date'], reverse=True)

    return render_template('main/positions_table.html',
                         project=project,
                         positions_data=positions_by_keyword)

@bp.route('/project/<int:project_id>/positions/changes')
@login_required
def project_positions_changes(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Get all keyword positions for the project
    positions = (KeywordPosition.query
                .join(Keyword)
                .filter(Keyword.project_id == project_id)
                .order_by(KeywordPosition.check_date.desc())
                .all())

    # Group positions by keyword and date
    positions_by_keyword = {}
    for pos in positions:
        keyword = pos.keyword.keyword
        if keyword not in positions_by_keyword:
            positions_by_keyword[keyword] = []
        positions_by_keyword[keyword].append({
            'date': pos.check_date.strftime('%Y-%m-%d'),
            'position': pos.position
        })

    # Sort positions for each keyword by date
    for keyword in positions_by_keyword:
        positions_by_keyword[keyword].sort(key=lambda x: x['date'], reverse=True)

    # Calculate position changes
    position_changes = []
    for keyword in positions_by_keyword:
        positions_list = positions_by_keyword[keyword]
        if len(positions_list) > 1:
            current_pos = positions_list[0]['position']
            previous_pos = positions_list[1]['position']
            change = previous_pos - current_pos
            position_changes.append({
                'keyword': keyword,
                'current_position': current_pos,
                'previous_position': previous_pos,
                'change': change
            })

    # Sort by absolute change value for biggest changes
    position_changes.sort(key=lambda x: abs(x['change']), reverse=True)

    return render_template('main/positions_changes.html',
                         project=project,
                         changes_data=position_changes)

@bp.route('/project/<int:project_id>/update', methods=['GET'])
@login_required
def update_project_data(project_id):
    try:
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            flash('У вас нет доступа к этому проекту', 'error')
            return redirect(url_for('main.dashboard'))

        # Здесь будет код обновления данных
        time.sleep(2)  # Имитация работы
        flash('Данные успешно обновлены', 'success')
        
        return redirect(url_for('main.project', id=project_id))

    except Exception as e:
        current_app.logger.error(f"Error updating data: {str(e)}")
        flash('Произошла ошибка при обновлении данных', 'error')
        return redirect(url_for('main.project', id=project_id))

@bp.route('/project/<int:id>/refresh', methods=['GET'])
@login_required
def refresh_project_data(id):
    try:
        project = Project.query.get_or_404(id)
        if project.user_id != current_user.id:
            flash('У вас нет доступа к этому проекту', 'error')
            return redirect(url_for('main.dashboard'))

        # Создаем API клиенты
        webmaster_api = YandexWebmasterAPI(
            oauth_token=project.yandex_webmaster_token,
            user_id=project.yandex_webmaster_user_id
        )
        metrika_api = YandexMetrikaAPI(project.yandex_metrika_token)

        # Обновляем данные по ключевым словам
        current_app.logger.info(f"Updating keyword data for project {id}")
        keywords_list = [(kw.keyword, kw) for kw in project.keywords]
        positions = webmaster_api.get_keywords_positions(project.yandex_webmaster_host, [kw for kw, _ in keywords_list])
        
        for keyword_text, keyword in keywords_list:
            try:
                if keyword_text in positions:
                    position, date = positions[keyword_text]
                    keyword_position = KeywordPosition(
                        keyword_id=keyword.id,
                        position=position,
                        date=date
                    )
                    db.session.add(keyword_position)
                    keyword.last_webmaster_update = datetime.utcnow()
                    current_app.logger.info(f"Updated position for keyword {keyword_text}: {position}")
                else:
                    current_app.logger.warning(f"No position data for keyword {keyword_text!r}")
            except Exception as e:
                current_app.logger.error(f"Error updating keyword {keyword_text}: {str(e)}")
                continue

        # Обновляем данные по URL
        current_app.logger.info(f"Updating URL data for project {id}")
        for url in project.urls:
            try:
                # Получаем трафик из Метрики за последние 7 дней
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
                
                # Получаем путь из URL
                path = urlparse(url.url).path
                
                traffic = metrika_api.get_pageviews(
                    counter_id=project.yandex_metrika_counter,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    filters=f"ym:pv:URLPath=='{path}'"
                )
                
                if traffic is not None:
                    url_traffic = URLTraffic(
                        url_id=url.id,
                        visits=traffic,
                        check_date=datetime.utcnow()
                    )
                    db.session.add(url_traffic)
                    url.last_metrika_update = datetime.utcnow()
                    current_app.logger.info(f"Updated traffic for URL {url.url}: {traffic}")
                else:
                    current_app.logger.warning(f"No traffic data for URL {url.url}")

            except Exception as e:
                current_app.logger.error(f"Error updating URL {url.url}: {str(e)}")
                continue

        # Сохраняем все изменения
        db.session.commit()
        current_app.logger.info(f"Successfully updated all data for project {id}")
        flash('Данные успешно обновлены', 'success')
        
        return redirect(url_for('main.project', id=id))

    except Exception as e:
        current_app.logger.error(f"Error updating data: {str(e)}")
        flash('Произошла ошибка при обновлении данных', 'error')
        return redirect(url_for('main.project', id=id))

@bp.route('/project/<int:project_id>/refresh_positions', methods=['POST'])
@login_required
def refresh_positions(project_id):
    try:
        current_app.logger.info(f"Получен запрос на обновление позиций для проекта {project_id}")
        
        project = Project.query.get_or_404(project_id)
        if project.user_id != current_user.id:
            current_app.logger.warning(f"Отказано в доступе к проекту {project_id} для пользователя {current_user.id}")
            return jsonify({
                'status': 'error',
                'message': 'У вас нет доступа к этому проекту'
            })

        # Проверяем, не запущен ли уже процесс
        pid_file = os.path.join(current_app.root_path, '..', 'logs', f'update_positions_{project_id}.pid')
        process_running = False
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                # Проверяем, существует ли процесс
                os.kill(pid, 0)  # Проверка существования процесса
                process_running = True
            except (ProcessLookupError, ValueError, OSError):
                # Если процесс не существует, удаляем pid файл
                try:
                    os.remove(pid_file)
                except OSError:
                    pass

        if process_running:
            current_app.logger.warning(f"Процесс обновления позиций для проекта {project_id} уже запущен (PID: {pid})")
            return jsonify({
                'status': 'error',
                'message': 'Процесс обновления уже запущен'
            })
        
        # Создаем директорию для логов если её нет
        log_dir = os.path.join(current_app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)

        current_app.logger.info(f"Запускаем обновление позиций для проекта {project_id}")
        
        # Запускаем процесс обновления позиций
        try:
            update_project_positions(project_id)
            current_app.logger.info(f"Процесс обновления позиций для проекта {project_id} успешно запущен")
            return jsonify({
                'status': 'success',
                'message': 'Процесс обновления позиций запущен'
            })
        except Exception as e:
            current_app.logger.error(f"Ошибка при запуске обновления позиций для проекта {project_id}: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            })

    except Exception as e:
        current_app.logger.error(f"Критическая ошибка при обработке запроса на обновление позиций: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@bp.route('/project/<int:project_id>/generate_test_data')
@login_required
def generate_test_data(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Получаем все ключевые слова проекта
    keywords = Keyword.query.filter_by(project_id=project_id).all()
    
    if not keywords:
        flash('Добавьте ключевые слова перед генерацией тестовых данных', 'error')
        return redirect(url_for('main.project_keywords', id=project_id))

    # Удаляем старые позиции
    KeywordPosition.query.filter(
        KeywordPosition.keyword_id.in_([k.id for k in keywords])
    ).delete(synchronize_session=False)

    # Генерируем 10 дат проверок
    base_date = datetime(2024, 12, 1)  # Начинаем с 1 декабря 2024
    check_dates = [base_date - timedelta(days=i*3) for i in range(10)]  # Каждые 3 дня

    # Для каждого ключевого слова генерируем позиции
    for keyword in keywords:
        # Определяем тренд для ключевого слова
        if keywords.index(keyword) == 0:  # Первое слово - рост
            start_pos = 50
            end_pos = 5
        elif keywords.index(keyword) == 1:  # Второе слово - падение
            start_pos = 10
            end_pos = 80
        else:  # Остальные - случайные колебания
            start_pos = 30
            end_pos = 40

        # Генерируем позиции с учетом тренда
        positions = []
        for i in range(10):
            progress = i / 9  # От 0 до 1
            base_position = start_pos + (end_pos - start_pos) * progress
            
            # Добавляем случайные колебания ±5 позиций
            from random import uniform
            position = max(1, base_position + uniform(-5, 5))
            
            # Создаем запись о позиции
            position_record = KeywordPosition(
                keyword_id=keyword.id,
                position=position,
                check_date=check_dates[i],
                data_date_start=check_dates[i] - timedelta(days=7),
                data_date_end=check_dates[i]
            )
            db.session.add(position_record)

    db.session.commit()
    flash('Тестовые данные успешно сгенерированы', 'success')
    return redirect(url_for('main.project_positions_report', project_id=project_id))

@bp.route('/project/<int:project_id>/positions/export')
@login_required
def export_positions(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Get filter parameters
    keyword = request.args.get('keyword', '')
    position_filter = request.args.get('position', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # Base query
    query = (KeywordPosition.query
             .join(Keyword)
             .filter(Keyword.project_id == project_id))

    # Apply filters
    if keyword:
        query = query.filter(Keyword.keyword.ilike(f'%{keyword}%'))

    if position_filter:
        if position_filter == 'top1':
            query = query.filter(KeywordPosition.position >= 1.0, KeywordPosition.position < 2.0)
        elif position_filter == 'top3':
            query = query.filter(KeywordPosition.position >= 1.0, KeywordPosition.position < 4.0)
        elif position_filter == 'top5':
            query = query.filter(KeywordPosition.position >= 1.0, KeywordPosition.position < 6.0)
        elif position_filter == 'top10':
            query = query.filter(KeywordPosition.position >= 1.0, KeywordPosition.position < 11.0)
        elif position_filter == 'top100':
            query = query.filter(KeywordPosition.position >= 100.0)

    if date_from:
        query = query.filter(KeywordPosition.date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(KeywordPosition.date <= datetime.strptime(date_to, '%Y-%m-%d'))

    # Get positions ordered by date and keyword
    positions = query.order_by(KeywordPosition.date.desc(), Keyword.keyword).all()

    # Create Excel file
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    # Add headers
    headers = ['Ключевое слово', 'Позиция', 'Дата']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    # Add data
    for row, position in enumerate(positions, 1):
        worksheet.write(row, 0, position.keyword.keyword)
        worksheet.write(row, 1, position.position)
        worksheet.write(row, 2, position.date.strftime('%Y-%m-%d'))

    workbook.close()
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'positions_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@bp.route('/test-chart')
@login_required
def test_chart():
    # Тестовые данные для графика
    data = {
        'dates': ['2024-12-28', '2024-12-29'],
        'positions': [8.5, 6.3]
    }
    return render_template('main/test_chart.html', title='Тестовый график', chart_data=data, zip=builtins.zip)

@bp.route('/project/<int:id>/update_status')
@login_required
def check_update_status(id):
    try:
        project = Project.query.get_or_404(id)
        if project.user_id != current_user.id:
            return jsonify({
                'status': 'error',
                'message': 'У вас нет доступа к этому проекту'
            })
        
        # Проверяем флаг в сессии
        session_key = f'update_completed_{id}'
        if session.get(session_key):
            # Если флаг установлен, сбрасываем его и возвращаем статус not_running
            session.pop(session_key, None)
            return jsonify({
                'status': 'not_running',
                'message': 'Процесс обновления не запущен'
            })
        
        # Проверяем наличие ошибок в логах
        try:
            log_file = os.path.join(current_app.root_path, '..', 'logs', 'update_positions.log')
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='cp1251') as f:
                    last_lines = f.readlines()[-10:]  # Читаем последние 10 строк
                    for line in reversed(last_lines):
                        if str(id) in line and 'ERROR' in line:
                            return jsonify({
                                'status': 'error',
                                'message': line.split('ERROR - ')[-1].strip()
                            })
        except Exception as e:
            current_app.logger.error(f"Ошибка при чтении лог-файла: {e}")
        
        # Проверяем, запущен ли процесс
        pid_file = os.path.join(current_app.root_path, '..', 'logs', f'update_positions_{id}.pid')
        process_running = False
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                # Проверяем, существует ли процесс
                os.kill(pid, 0)  # Проверка существования процесса
                process_running = True
            except (ProcessLookupError, ValueError, OSError):
                # Если процесс не существует, удаляем pid файл
                try:
                    os.remove(pid_file)
                except OSError:
                    pass

        if process_running:
            return jsonify({
                'status': 'running',
                'message': 'Процесс обновления позиций выполняется'
            })
        
        # Проверяем, было ли обновление успешным
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        recent_update = KeywordPosition.query.join(Keyword).filter(
            Keyword.project_id == id,
            KeywordPosition.check_date >= one_minute_ago
        ).first()
        
        if recent_update:
            # Устанавливаем флаг в сессии
            session[session_key] = True
            return jsonify({
                'status': 'completed',
                'success': True,
                'message': 'Позиции успешно обновлены'
            })
        
        return jsonify({
            'status': 'not_running',
            'message': 'Процесс обновления не запущен'
        })
            
    except Exception as e:
        current_app.logger.error(f"Ошибка при проверке статуса: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@bp.route('/project/<int:project_id>/traffic/report')
@login_required
def traffic_report(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Получаем параметры фильтров
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_traffic = request.args.get('min_traffic', type=int)
    url_filter = request.args.get('url_filter')

    # Базовый запрос
    query = (URLTraffic.query
             .join(URL)
             .filter(URL.project_id == project_id))

    # Применяем фильтры
    if date_from:
        query = query.filter(URLTraffic.check_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(URLTraffic.check_date <= datetime.strptime(date_to, '%Y-%m-%d'))
    if url_filter:
        url_filter = url_filter.replace('*', '%')
        query = query.filter(URL.url.like(url_filter))

    # Получаем все записи о трафике
    traffic_records = query.order_by(URLTraffic.check_date.desc()).all()

    # Группируем данные по URL и датам
    traffic_data = {}
    dates = set()
    for record in traffic_records:
        url = record.url.url
        date = record.check_date.strftime('%Y-%m-%d')
        dates.add(date)
        
        if url not in traffic_data:
            traffic_data[url] = {}
        traffic_data[url][date] = record.visits

    # Сортируем даты
    dates = sorted(list(dates))

    # Формируем данные для таблицы
    table_data = []
    for url in sorted(traffic_data.keys()):
        url_traffic = []
        prev_value = None
        
        for date in dates:
            value = traffic_data[url].get(date)
            change = 0
            change_value = ''
            
            if value is not None and prev_value is not None:
                change = value - prev_value
                change_value = f"{'+' if change > 0 else ''}{change}"
            
            url_traffic.append({
                'value': value if value is not None else '-',
                'change': change,
                'change_value': change_value
            })
            
            if value is not None:
                prev_value = value
        
        # Применяем фильтр по минимальному трафику
        if min_traffic is None or any(t['value'] != '-' and t['value'] >= min_traffic for t in url_traffic):
            table_data.append({
                'url': url,
                'traffic': url_traffic
            })

    # Вычисляем средние значения
    averages = []
    for i in range(len(dates)):
        values = [data['traffic'][i]['value'] for data in table_data 
                 if data['traffic'][i]['value'] != '-']
        avg = sum(values) / len(values) if values else 0
        averages.append(round(avg, 1))

    # Данные для графика
    chart_data = {
        'labels': dates,
        'values': averages
    }

    return render_template('main/traffic_report.html',
                         title='Отчет по трафику',
                         project=project,
                         dates=dates,
                         traffic_data=table_data,
                         averages=averages,
                         chart_data=chart_data)

@bp.route('/project/<int:project_id>/traffic/export')
@login_required
def export_traffic(project_id):
    # Получаем те же данные, что и для отчета
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('У вас нет доступа к этому проекту', 'error')
        return redirect(url_for('main.dashboard'))

    # Получаем параметры фильтров
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    min_traffic = request.args.get('min_traffic', type=int)
    url_filter = request.args.get('url_filter')

    # Базовый запрос
    query = (URLTraffic.query
             .join(URL)
             .filter(URL.project_id == project_id))

    # Применяем фильтры
    if date_from:
        query = query.filter(URLTraffic.check_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(URLTraffic.check_date <= datetime.strptime(date_to, '%Y-%m-%d'))
    if url_filter:
        url_filter = url_filter.replace('*', '%')
        query = query.filter(URL.url.like(url_filter))

    # Получаем все записи о трафике
    traffic_records = query.order_by(URLTraffic.check_date.desc()).all()

    # Создаем Excel файл
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    # Форматирование
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#F3F4F6',
        'border': 1
    })

    # Записываем заголовки
    worksheet.write(0, 0, 'URL', header_format)
    worksheet.write(0, 1, 'Дата проверки', header_format)
    worksheet.write(0, 2, 'Трафик', header_format)
    worksheet.write(0, 3, 'Изменение', header_format)

    # Записываем данные
    row = 1
    for record in traffic_records:
        worksheet.write(row, 0, record.url.url)
        worksheet.write(row, 1, record.check_date.strftime('%Y-%m-%d'))
        worksheet.write(row, 2, record.visits)
        
        # Находим предыдущую запись для этого URL
        prev_record = URLTraffic.query.join(URL).filter(
            URL.id == record.url.id,
            URLTraffic.check_date < record.check_date
        ).order_by(URLTraffic.check_date.desc()).first()
        
        if prev_record:
            change = record.visits - prev_record.visits
            worksheet.write(row, 3, change)
        
        row += 1

    workbook.close()
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'traffic_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )
