from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, URL, Optional

class ProjectForm(FlaskForm):
    name = StringField('Название проекта', validators=[DataRequired(), Length(max=100)])
    yandex_metrika_counter = StringField('ID счетчика Яндекс.Метрики', validators=[Optional()])
    yandex_metrika_token = StringField('Токен Яндекс.Метрики', validators=[Optional()])
    yandex_webmaster_host = StringField('Хост в Яндекс.Вебмастере', validators=[Optional()])
    submit = SubmitField('Создать проект')
