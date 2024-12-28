from flask import render_template, flash, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db, socketio, csrf
from app.main import bp
from app.main.forms import ProjectForm
from flask_wtf import FlaskForm
from app.models import Project, User, Keyword, KeywordPosition, URL, URLTraffic, Region
from app.yandex import YandexMetrikaAPI, YandexWebmasterAPI
from datetime import datetime, timedelta
import logging
import threading
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class KeywordForm(FlaskForm):
    pass

class URLForm(FlaskForm):
    pass

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
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    return render_template('main/project.html', title=project.name, project=project)

@bp.route('/project/<int:id>/keywords', methods=['GET', 'POST'])
@login_required
def project_keywords(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.dashboard'))
    
    form = KeywordForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        region_id = request.form.get('region_id')
        if not region_id:
            flash('Необходимо выбрать регион', 'error')
            return redirect(url_for('main.project_keywords', id=id))
        
        # Проверяем существование региона
        region = Region.query.get(region_id)
        if not region:
            flash('Выбранный регион не существует', 'error')
            return redirect(url_for('main.project_keywords', id=id))
        
        keywords_text = request.form.get('keywords', '').strip()
        if not keywords_text:
            flash('Список ключевых слов не может быть пустым', 'error')
            return redirect(url_for('main.project_keywords', id=id))
        
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
                project_id=id,
                region_id=region_id,
                keyword=keyword_text
            ).first()
            
            if existing_keyword:
                skipped_count += 1
                continue
                
            keyword = Keyword(
                keyword=keyword_text,
                project_id=id,
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
        return redirect(url_for('main.project_keywords', id=id))
    
    # Получаем список регионов для формы
    regions = Region.query.order_by(Region.name).all()
    
    return render_template('main/keywords.html', 
                         title='Keywords', 
                         project=project, 
                         keywords=project.keywords,
                         regions=regions,
                         KeywordPosition=KeywordPosition,
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
    else:
        flash('Ошибка валидации формы', 'error')
    
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
    else:
        flash('Ошибка валидации формы', 'error')
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:project_id>/keywords/<int:keyword_id>/delete', methods=['POST'])
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
        
        db.session.delete(keyword)
        db.session.commit()
        flash('Ключевое слово удалено', 'success')
    else:
        flash('Ошибка валидации формы', 'error')
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

@bp.route('/project/<int:project_id>/keywords/clear_all', methods=['POST'])
@login_required
def clear_all_keywords(project_id):
    form = KeywordForm()
    if form.validate_on_submit():
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
    else:
        flash('Ошибка валидации формы', 'error')
    
    return redirect(url_for('main.project_keywords', id=project_id))

@bp.route('/project/<int:id>/update', methods=['GET'])
@login_required
def update_project_data(id):
    try:
        project = Project.query.get_or_404(id)
        if project.user_id != current_user.id:
            flash('У вас нет доступа к этому проекту', 'error')
            return redirect(url_for('main.dashboard'))

        # Здесь будет код обновления данных
        time.sleep(2)  # Имитация работы
        flash('Данные успешно обновлены', 'success')
        
        return redirect(url_for('main.project', id=id))

    except Exception as e:
        current_app.logger.error(f"Error updating data: {str(e)}")
        flash('Произошла ошибка при обновлении данных', 'error')
        return redirect(url_for('main.project', id=id))

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
                        visitors=traffic,
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

@bp.route('/project/<int:id>/refresh_positions', methods=['GET'])
@login_required
def refresh_positions(id):
    try:
        project = Project.query.get_or_404(id)
        if project.user_id != current_user.id:
            flash('У вас нет доступа к этому проекту', 'error')
            return redirect(url_for('main.dashboard'))

        # Создаем клиент API
        api = YandexWebmasterAPI(
            oauth_token=project.yandex_webmaster_token,
            user_id=project.yandex_webmaster_user_id
        )

        # Получаем все ключевые слова проекта
        keywords = [kw.keyword for kw in project.keywords]
        if not keywords:
            flash('У проекта нет ключевых слов для обновления', 'error')
            return redirect(url_for('main.project', id=id))

        # Получаем позиции для всех ключевых слов
        positions = api.get_keywords_positions(project.yandex_webmaster_host, keywords)
        
        if positions is None:  # Явно проверяем на None
            flash('Ошибка при получении данных от API Яндекс.Вебмастер. Проверьте логи для деталей.', 'error')
            return redirect(url_for('main.project', id=id))
            
        if not positions:
            flash('Не удалось получить позиции ни для одного ключевого слова', 'error')
            return redirect(url_for('main.project', id=id))

        # Обновляем позиции в базе данных
        success_count = 0
        error_count = 0
        for keyword_text, (position, date_range) in positions.items():
            if position is not None:
                keyword = Keyword.query.filter_by(
                    project_id=id,
                    keyword=keyword_text
                ).first()
                
                if keyword:
                    try:
                        # Создаем новую запись в таблице KeywordPosition
                        keyword_position = KeywordPosition(
                            keyword_id=keyword.id,
                            position=position,
                            check_date=datetime.utcnow()
                        )
                        
                        # Парсим даты из строки формата "dd.mm - dd.mm"
                        if date_range:
                            start_date_str, end_date_str = date_range.split(' - ')
                            current_year = datetime.now().year
                            
                            # Преобразуем строки дат в объекты datetime
                            start_date = datetime.strptime(f"{start_date_str}.{current_year}", '%d.%m.%Y')
                            end_date = datetime.strptime(f"{end_date_str}.{current_year}", '%d.%m.%Y')
                            
                            # Устанавливаем даты
                            keyword_position.data_date_start = start_date
                            keyword_position.data_date_end = end_date
                            
                        db.session.add(keyword_position)
                        keyword.last_webmaster_update = datetime.utcnow()
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении позиции для '{keyword_text}': {e}")
                        error_count += 1

        if success_count > 0:
            db.session.commit()
            message = f'Успешно обновлено {success_count} из {len(keywords)} ключевых слов'
            if error_count > 0:
                message += f' (ошибок: {error_count})'
            flash(message, 'success')
        else:
            db.session.rollback()
            flash('Не удалось обновить ни одно ключевое слово', 'error')
            
        return redirect(url_for('main.project', id=id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка при обновлении позиций: {str(e)}")
        flash(f'Ошибка при обновлении позиций: {str(e)}', 'error')
        return redirect(url_for('main.project', id=id))
