from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class CreateUserForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Повторите пароль', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Роль', choices=[('user', 'Пользователь'), ('admin', 'Администратор')], validators=[DataRequired()])
    submit = SubmitField('Создать пользователя')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Это имя пользователя уже занято.')
            
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Этот email уже используется.')

class EditUserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = SelectField('Роль', choices=[('user', 'Пользователь'), ('admin', 'Администратор')], validators=[DataRequired()])
    submit = SubmitField('Сохранить изменения')
    
    def __init__(self, original_email, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        self.original_email = original_email
        
    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError('Этот email уже используется.')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField('Повторите новый пароль', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Изменить пароль')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Восстановить пароль')
