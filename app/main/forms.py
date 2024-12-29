from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, URL, Optional

class ProjectForm(FlaskForm):
    name = StringField('Название проекта', validators=[DataRequired(), Length(max=100)])
    yandex_metrika_counter = StringField('ID счетчика Яндекс.Метрики', validators=[DataRequired(), Length(max=50)])
    yandex_metrika_token = StringField('Токен Яндекс.Метрики', validators=[DataRequired(), Length(max=100)])
    yandex_webmaster_host = StringField('Хост в Яндекс.Вебмастере', validators=[DataRequired(), Length(max=200)])
    yandex_webmaster_token = StringField('Токен Яндекс.Вебмастера', validators=[DataRequired(), Length(max=100)])
    yandex_webmaster_user_id = StringField('User ID Яндекс.Вебмастера', validators=[DataRequired(), Length(max=50)])
    
    # Скрытые поля для хранения статуса валидации
    metrika_validated = HiddenField('Метрика проверена', default='false')
    webmaster_validated = HiddenField('Вебмастер проверен', default='false')
    
    validate_metrika = SubmitField('Проверить Яндекс.Метрику')
    validate_webmaster = SubmitField('Проверить Яндекс.Вебмастер')
    submit = SubmitField('Создать проект')

class KeywordForm(FlaskForm):
    keywords = TextAreaField('Ключевые слова', validators=[DataRequired()])
    submit = SubmitField('Добавить ключевые слова')

class URLForm(FlaskForm):
    urls = TextAreaField('URLs', validators=[DataRequired()])
    submit = SubmitField('Добавить URLs')
