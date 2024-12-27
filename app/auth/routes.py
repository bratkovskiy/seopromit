from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, CreateUserForm, EditUserForm, ChangePasswordForm, ResetPasswordRequestForm
from app.models import User
from app.decorators import admin_required
from app.email import send_email

def generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Неверное имя пользователя или пароль', 'error')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('main.dashboard'))
    return render_template('auth/login.html', title='Вход', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template('auth/users.html', title='Пользователи', users=users)

@bp.route('/user/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, 
                   email=form.email.data,
                   role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Пользователь успешно создан', 'success')
        return redirect(url_for('auth.users'))
    return render_template('auth/create_user.html', title='Создание пользователя', form=form)

@bp.route('/user/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    form = EditUserForm(user.email)
    if form.validate_on_submit():
        user.email = form.email.data
        user.role = form.role.data
        db.session.commit()
        flash('Изменения сохранены', 'success')
        return redirect(url_for('auth.users'))
    elif request.method == 'GET':
        form.email.data = user.email
        form.role.data = user.role
    return render_template('auth/edit_user.html', title='Редактирование пользователя',
                         form=form, user=user)

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Неверный текущий пароль', 'error')
            return redirect(url_for('auth.change_password'))
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Пароль успешно изменен', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('auth/change_password.html', title='Изменение пароля', form=form)

@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            new_password = generate_password()
            user.set_password(new_password)
            db.session.commit()
            
            send_email(
                'Восстановление пароля SEOPromIT',
                user.email,
                f'Здравствуйте!\n\nВаш новый пароль: {new_password}\n\n'
                f'Рекомендуем сменить его после входа в систему.\n\n'
                f'С уважением,\nКоманда SEOPromIT'
            )
            flash('На указанный email отправлены инструкции по восстановлению пароля', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Пользователь с таким email не найден', 'error')
    return render_template('auth/reset_password_request.html', title='Восстановление пароля', form=form)
