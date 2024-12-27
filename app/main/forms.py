from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, URL, Optional

class ProjectForm(FlaskForm):
    name = StringField('Название проекта', validators=[DataRequired(), Length(max=100)])
    yandex_metrika_counter = StringField('ID счетчика Яндекс.Метрики', validators=[DataRequired()])
    yandex_metrika_token = StringField('Токен Яндекс.Метрики', validators=[DataRequired()])
    yandex_webmaster_host = StringField('Хост в Яндекс.Вебмастере', validators=[DataRequired()])
    yandex_webmaster_token = StringField('Токен Яндекс.Вебмастера', validators=[DataRequired()])
    yandex_webmaster_user_id = StringField('User ID Яндекс.Вебмастера', validators=[DataRequired()])
    
    # Скрытые поля для хранения статуса валидации
    metrika_validated = HiddenField('Метрика проверена', default='false')
    webmaster_validated = HiddenField('Вебмастер проверен', default='false')
    
    validate_metrika = SubmitField('Проверить Яндекс.Метрику')
    validate_webmaster = SubmitField('Проверить Яндекс.Вебмастер')
    submit = SubmitField('Создать проект')
