from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FileField
from wtforms.validators import DataRequired, Length, EqualTo
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from wtforms import TextAreaField

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

def validate_class_count(form, field):
    if len(field.data) > 2:
        raise ValidationError('Можно выбрать не более двух классов.')

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6, max=25)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Роль', choices=[('admin', 'Админ'), ('teacher', 'Учитель'), ('parent', 'Родитель')], validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


class AddStudentForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=1, max=255)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=1, max=255)])
    middle_name = StringField('Отчество', validators=[DataRequired(), Length(min=1, max=255)])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    photo = FileField('Фото', validators=[DataRequired()])
    submit = SubmitField('Добавить')


class TeacherRegistrationForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    middle_name = StringField('Отчество', validators=[DataRequired()])
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    class_id = MultiCheckboxField('Классы', coerce=int, validators=[validate_class_count])
    submit = SubmitField('Добавить')


class TeacherEditForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    middle_name = StringField('Отчество', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired()])
    education = TextAreaField('Образование', validators=[DataRequired()])
    experience = TextAreaField('Опыт', validators=[DataRequired()])
    photo = FileField('Фото', validators=[DataRequired()])
    class_id = MultiCheckboxField('Классы', coerce=int, validators=[validate_class_count])
    submit = SubmitField('Сохранить')



class StudentRegistrationForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=2, max=255)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=2, max=255)])
    middle_name = StringField('Отчество', validators=[DataRequired(), Length(min=2, max=255)])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    photo = FileField('Фотография', validators=[DataRequired()])
    submit = SubmitField('Добавить')
