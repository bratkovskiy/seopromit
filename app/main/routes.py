from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.main import bp
from app.models import Project, Keyword, URL, KeywordPosition, URLTraffic
from app.main.forms import ProjectForm
from datetime import datetime

@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('main/dashboard.html', title='Dashboard', projects=projects)

@bp.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            yandex_metrika_counter=form.yandex_metrika_counter.data,
            yandex_metrika_token=form.yandex_metrika_token.data,
            yandex_webmaster_host=form.yandex_webmaster_host.data,
            user_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('main/new_project.html', title='New Project', form=form)

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
