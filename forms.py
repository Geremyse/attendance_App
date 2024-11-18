from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FileField
from wtforms.validators import DataRequired, Length, EqualTo

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
    name = StringField('ФИО ученика', validators=[DataRequired(), Length(min=1, max=255)])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    photo = FileField('Фотография', validators=[DataRequired()])
    submit = SubmitField('Добавить студента')


class TeacherRegistrationForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=1, max=255)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=1, max=255)])
    middle_name = StringField('Отчество', validators=[DataRequired(), Length(min=1, max=255)])
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=1, max=255)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=1, max=255)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить')

class TeacherEditForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=1, max=255)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=1, max=255)])
    middle_name = StringField('Отчество', validators=[DataRequired(), Length(min=1, max=255)])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class StudentRegistrationForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired(), Length(min=2, max=255)])
    first_name = StringField('Имя', validators=[DataRequired(), Length(min=2, max=255)])
    middle_name = StringField('Отчество', validators=[DataRequired(), Length(min=2, max=255)])
    class_id = SelectField('Класс', coerce=int, validators=[DataRequired()])
    photo = FileField('Фотография', validators=[DataRequired()])
    submit = SubmitField('Добавить')
