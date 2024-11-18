from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, FileField
from wtforms.validators import DataRequired, Length, EqualTo
import mysql.connector
import cv2
import face_recognition
from datetime import datetime
from flask_socketio import SocketIO, emit
import base64
import threading
from functools import wraps
from flask import abort
from forms import LoginForm, RegisterForm, AddStudentForm, TeacherRegistrationForm, StudentRegistrationForm, TeacherEditForm
import os
import json
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'known_faces'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="attendance_db"
    )

def load_known_faces():
    known_faces_dir = 'known_faces'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CONCAT(last_name, ' ', first_name, ' ', middle_name), face_encoding FROM students")
    students = cursor.fetchall()
    cursor.close()
    conn.close()

    known_face_encodings = []
    known_face_names = []

    for name, face_encoding in students:
        filename = f"{face_encoding}.jpg"
        file_path = os.path.join(known_faces_dir, filename)
        if os.path.exists(file_path):
            image = face_recognition.load_image_file(file_path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(name)
            else:
                print(f"No face found in {filename}")
        else:
            print(f"File {filename} not found")

    return known_face_encodings, known_face_names

load_known_faces()

# Глобальная переменная для управления захватом видео
capture_active = False

# Захват изображений и распознавание лиц

import cv2
import face_recognition
import base64
from PIL import Image, ImageDraw, ImageFont
import numpy as np

def capture_and_recognize():
    global capture_active
    video_capture = cv2.VideoCapture(1)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Уменьшение разрешения
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Уменьшение разрешения

    frame_count = 0
    process_every_n_frames = 5  # Обработка каждого пятого кадра

    known_face_encodings, known_face_names = load_known_faces()

    while capture_active:
        ret, frame = video_capture.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % process_every_n_frames == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                name = "Unknown"

                if True in matches:
                    first_match_index = matches.index(True)
                    name = known_face_names[first_match_index]
                    record_attendance(name)

                # Отображение имени на изображении
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)

                # Использование Pillow для рендеринга текста с поддержкой кириллицы
                pil_image = Image.fromarray(frame)
                draw = ImageDraw.Draw(pil_image)
                font = ImageFont.truetype("arial.ttf", 20)  # Убедитесь, что у вас есть шрифт, поддерживающий кириллицу
                draw.text((left + 6, bottom - 30), name, font=font, fill=(255, 255, 255))
                frame = np.array(pil_image)

            # Преобразование кадра в base64 для передачи через WebSocket
            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            socketio.emit('frame', {'image': frame_base64})

    video_capture.release()
    cv2.destroyAllWindows()

# Запись данных о посещаемости
def record_attendance(student_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM students WHERE CONCAT(last_name, ' ', first_name, ' ', middle_name) = %s", (student_name,))
    student = cursor.fetchone()
    if student is None:
        print(f"Student with name {student_name} not found in the database.")
        cursor.close()
        conn.close()
        return

    student_id = student[0]
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Проверка, была ли уже записана посещаемость для данного ученика в текущий день
    cursor.execute("SELECT * FROM attendance WHERE student_id = %s AND DATE(attendance_time) = %s", (student_id, current_date))
    existing_record = cursor.fetchone()

    if not existing_record:
        query = "INSERT INTO attendance (student_id, attendance_time) VALUES (%s, %s)"
        values = (student_id, current_time)
        cursor.execute(query, values)
        conn.commit()

        # Отправка обновления через WebSocket
        socketio.emit('attendance_update', {'data': [(student_name, current_time)]})

    cursor.close()
    conn.close()

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('get_attendance_updates')
def handle_get_attendance_updates():
    while True:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT CONCAT(students.last_name, ' ', students.first_name, ' ', students.middle_name), attendance.attendance_time FROM attendance JOIN students ON attendance.student_id = students.id")
        attendance_data = cursor.fetchall()
        cursor.close()
        conn.close()
        socketio.emit('attendance_update', {'data': attendance_data})
        socketio.sleep(5)  # Обновлять каждые 5 секунд

# Модель пользователя
class User(UserMixin):
    def __init__(self, id, username, password, role, last_name=None, first_name=None, middle_name=None):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.last_name = last_name
        self.first_name = first_name
        self.middle_name = middle_name

    def is_admin(self):
        return self.role == 'admin'

    def is_teacher(self):
        return self.role == 'teacher'

    def is_parent(self):
        return self.role == 'parent'


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, teacher_id, parent_id FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        role = user[3]
        if role == 'teacher':
            cursor.execute("SELECT last_name, first_name, middle_name FROM teachers WHERE id = %s", (user[4],))
            teacher_data = cursor.fetchone()
            if teacher_data:
                last_name, first_name, middle_name = teacher_data
            else:
                last_name, first_name, middle_name = None, None, None
        elif role == 'parent':
            # Предположим, что у родителей есть таблица parents с аналогичными полями
            cursor.execute("SELECT last_name, first_name, middle_name FROM parents WHERE id = %s", (user[5],))
            parent_data = cursor.fetchone()
            if parent_data:
                last_name, first_name, middle_name = parent_data
            else:
                last_name, first_name, middle_name = None, None, None
        else:
            last_name, first_name, middle_name = None, None, None

        cursor.close()
        conn.close()
        return User(user[0], user[1], user[2], user[3], last_name, first_name, middle_name)
    return None


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(403)
            if role == 'admin' and not current_user.is_admin():
                return abort(403)
            if role == 'teacher' and not current_user.is_teacher():
                return abort(403)
            if role == 'parent' and not current_user.is_parent():
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
@login_required
def index():
    if current_user.is_admin():
        return redirect(url_for('admin_dashboard'))
    elif current_user.is_teacher():
        return redirect(url_for('teacher_dashboard'))
    elif current_user.is_parent():
        return redirect(url_for('parent_dashboard'))
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/teachers', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_teachers():
    form = TeacherRegistrationForm()
    form.class_id.choices = [(row[0], row[1]) for row in get_classes()]
    if form.validate_on_submit():
        last_name = form.last_name.data
        first_name = form.first_name.data
        middle_name = form.middle_name.data
        username = form.username.data
        password = form.password.data
        class_id = form.class_id.data

        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверка уникальности username
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash('Имя пользователя уже существует', 'danger')
            return redirect(url_for('admin_teachers'))

        cursor.execute("INSERT INTO teachers (last_name, first_name, middle_name, class_id) VALUES (%s, %s, %s, %s)",
                       (last_name, first_name, middle_name, class_id))
        teacher_id = cursor.lastrowid
        cursor.execute("INSERT INTO users (username, password, role, teacher_id) VALUES (%s, %s, %s, %s)",
                       (username, password, 'teacher', teacher_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Учитель добавлен успешно', 'success')
        return redirect(url_for('admin_teachers'))

    teachers = get_teachers()
    return render_template('admin_teachers.html', form=form, teachers=teachers)


@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_students():
    form = StudentRegistrationForm()
    form.class_id.choices = [(row[0], row[1]) for row in get_classes()]

    if form.validate_on_submit():
        last_name = form.last_name.data
        first_name = form.first_name.data
        middle_name = form.middle_name.data
        class_id = form.class_id.data
        photo = form.photo.data
        if photo and allowed_file(photo.filename):
            face_encoding = random.randint(100000, 999999)  # Генерация случайного числа для face_encoding
            filename = f"{face_encoding}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO students (last_name, first_name, middle_name, face_encoding, class_id) VALUES (%s, %s, %s, %s, %s)",
                           (last_name, first_name, middle_name, face_encoding, class_id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Ученик добавлен успешно', 'success')
            return redirect(url_for('admin_students'))
        else:
            flash('Неверный формат файла', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')

    students = get_students()
    return render_template('admin_students.html', form=form, students=students)


@app.route('/admin/classes', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_classes():
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO classes (name) VALUES (%s)", (class_name,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Класс добавлен успешно', 'success')
        return redirect(url_for('admin_classes'))

    classes = get_classes()
    return render_template('admin_classes.html', classes=classes)

def get_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT students.*, classes.name FROM students JOIN classes ON students.class_id = classes.id")
    students = cursor.fetchall()
    cursor.close()
    conn.close()

    # Отладочная информация
    print("Students data fetched from the database:")
    for student in students:
        print(student)

    return students

def get_teachers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT teachers.*, users.username, users.password, users.role, classes.name
        FROM teachers
        JOIN users ON teachers.id = users.teacher_id
        JOIN classes ON teachers.class_id = classes.id
    """)
    teachers = cursor.fetchall()
    cursor.close()
    conn.close()

    # Отладочная информация
    print("Teachers data fetched from the database:")
    for teacher in teachers:
        print(teacher)

    return teachers



@app.route('/teacher')
@login_required
@role_required('teacher')
def teacher_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CONCAT(students.last_name, ' ', students.first_name, ' ', students.middle_name), classes.name, attendance.attendance_time FROM attendance JOIN students ON attendance.student_id = students.id JOIN classes ON students.class_id = classes.id")
    attendance_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('teacher_dashboard.html', attendance_data=attendance_data)

@app.route('/teacher/add_student', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def add_student():
    form = AddStudentForm()
    form.class_id.choices = [(row[0], row[1]) for row in get_classes()]
    if form.validate_on_submit():
        print("Form validated successfully")
        name = form.name.data
        class_id = form.class_id.data
        photo = form.photo.data
        if photo and allowed_file(photo.filename):
            face_encoding = random.randint(100000, 999999)  # Генерация случайного числа для face_encoding
            filename = f"{face_encoding}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO students (name, face_encoding, class_id) VALUES (%s, %s, %s)", (name, face_encoding, class_id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Student added successfully', 'success')
            return redirect(url_for('teacher_dashboard'))
        else:
            print("Invalid file format")
            flash('Invalid file format', 'danger')
    else:
        print("Form validation failed")
        for field, errors in form.errors.items():
            for error in errors:
                print(f"Error in {field}: {error}")
    return render_template('add_student.html', form=form)

def get_classes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM classes")
    classes = cursor.fetchall()
    cursor.close()
    conn.close()
    return classes

@app.route('/parent')
@login_required
@role_required('parent')
def parent_dashboard():
    # Логика для панели родителя
    return render_template('parent_dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        print("Form validated successfully")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (form.username.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and user[2] == form.password.data:
            print("User authenticated successfully")
            login_user(User(user[0], user[1], user[2], user[3], user[4], user[5]))
            return redirect(url_for('index'))
        else:
            print("Login failed")
            flash('Login Unsuccessful. Check username and password', 'danger')
    else:
        print("Form validation failed")
        for field, errors in form.errors.items():
            for error in errors:
                print(f"Error in {field}: {error}")
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        print("Form validated successfully")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (form.username.data,))
        user = cursor.fetchone()
        if user:
            print("User already exists")
            flash('Username already exists', 'danger')
        else:
            print("Creating new user")
            role = form.role.data  # Получаем выбранную роль из формы
            print(f"Role: {role}")
            cursor.execute("INSERT INTO users (username, password, role, last_name, first_name, middle_name) VALUES (%s, %s, %s, %s, %s, %s)",
                           (form.username.data, form.password.data, role, form.last_name.data, form.first_name.data, form.middle_name.data))
            conn.commit()
            flash('Account created successfully', 'success')
            return redirect(url_for('login'))
        cursor.close()
        conn.close()
    else:
        print("Form validation failed")
        for field, errors in form.errors.items():
            for error in errors:
                print(f"Error in {field}: {error}")
    return render_template('register.html', form=form)

@app.route('/admin/teachers/edit/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_teacher(teacher_id):
    form = TeacherEditForm()
    form.class_id.choices = [(row[0], row[1]) for row in get_classes()]

    if request.method == 'POST' and form.validate_on_submit():
        last_name = form.last_name.data
        first_name = form.first_name.data
        middle_name = form.middle_name.data
        class_id = form.class_id.data

        print(f"Form data: last_name={last_name}, first_name={first_name}, middle_name={middle_name}, class_id={class_id}")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Обновление учителя в таблице teachers
            cursor.execute("UPDATE teachers SET last_name = %s, first_name = %s, middle_name = %s, class_id = %s WHERE id = %s",
                           (last_name, first_name, middle_name, class_id, teacher_id))

            conn.commit()
            flash('Учитель обновлен успешно', 'success')
        except Exception as e:
            print(f"Error updating teacher: {str(e)}")
            flash(f'Ошибка при обновлении учителя: {str(e)}', 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('admin_teachers'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT teachers.*, users.username, users.password
        FROM teachers
        JOIN users ON teachers.id = users.teacher_id
        WHERE teachers.id = %s
    """, (teacher_id,))
    teacher = cursor.fetchone()
    cursor.close()
    conn.close()

    # Отладочная информация
    print("Teacher data fetched from the database:", teacher)

    if teacher:
        form.last_name.data = teacher[1]
        form.first_name.data = teacher[2]
        form.middle_name.data = teacher[3]
        form.class_id.data = teacher[4]

    return render_template('edit_teacher.html', form=form, teacher_id=teacher_id)


@app.route('/admin/teachers/delete/<int:teacher_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_teacher(teacher_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Начинаем транзакцию
        conn.start_transaction()

        # Удаление учителя из таблицы teachers
        cursor.execute("DELETE FROM teachers WHERE id = %s", (teacher_id,))

        # Удаление связанной записи из таблицы users
        cursor.execute("DELETE FROM users WHERE teacher_id = %s", (teacher_id,))

        # Подтверждаем транзакцию
        conn.commit()
        flash('Учитель удален успешно', 'success')

    except Exception as e:
        # Откатываем транзакцию в случае ошибки
        conn.rollback()
        flash(f'Ошибка при удалении учителя: {str(e)}', 'danger')

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_teachers'))




@app.route('/admin/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_student(student_id):
    form = StudentRegistrationForm()
    form.class_id.choices = [(row[0], row[1]) for row in get_classes()]

    if request.method == 'POST' and form.validate_on_submit():
        last_name = form.last_name.data
        first_name = form.first_name.data
        middle_name = form.middle_name.data
        class_id = form.class_id.data
        photo = form.photo.data

        if photo and allowed_file(photo.filename):
            face_encoding = random.randint(100000, 999999)  # Генерация случайного числа для face_encoding
            filename = f"{face_encoding}.jpg"
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET last_name = %s, first_name = %s, middle_name = %s, face_encoding = %s, class_id = %s WHERE id = %s",
                           (last_name, first_name, middle_name, face_encoding, class_id, student_id))
            conn.commit()
            cursor.close()
            conn.close()
            flash('Ученик обновлен успешно', 'success')
            return redirect(url_for('admin_students'))
        else:
            flash('Неверный формат файла', 'danger')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    student = cursor.fetchone()
    cursor.close()
    conn.close()

    if student:
        form.last_name.data = student[1]
        form.first_name.data = student[2]
        form.middle_name.data = student[3]
        form.class_id.data = student[5]

    return render_template('edit_student.html', form=form, student_id=student_id)



@app.route('/admin/students/delete/<int:student_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_student(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Начинаем транзакцию
        conn.start_transaction()

        # Удаление студента из таблицы students
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))

        # Подтверждаем транзакцию
        conn.commit()
        flash('Ученик удален успешно', 'success')

    except Exception as e:
        # Откатываем транзакцию в случае ошибки
        conn.rollback()
        flash(f'Ошибка при удалении ученика: {str(e)}', 'danger')

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_students'))




@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/capture')
@login_required
@role_required('teacher')
def capture():
    global capture_active
    capture_active = True
    threading.Thread(target=capture_and_recognize).start()
    return jsonify({"status": "Capturing and recognizing faces..."})

@app.route('/stop_capture')
@login_required
@role_required('teacher')
def stop_capture():
    global capture_active
    capture_active = False
    return jsonify({"status": "Stopped capturing"})

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
