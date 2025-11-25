from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# --- basic config ---
app.config['SECRET_KEY'] = 'change-this-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///collab_todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    tasks_assigned = db.relationship('Task', backref='assignee', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    tasks = db.relationship('Task', backref='project', lazy=True)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='todo')

    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('loading'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('loading'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('loading'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('loading'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please fill all fields', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Account created. Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/loading')
@login_required
def loading():
    # Just show loading animation, then front-end JS will redirect to dashboard
    return render_template('loading.html')


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # Ensure the user has at least one project
    project = Project.query.filter_by(owner_id=current_user.id).first()
    if not project:
        project = Project(name=f"{current_user.username}'s Project", owner_id=current_user.id)
        db.session.add(project)
        db.session.commit()

    # Handle new task creation
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        deadline_str = request.form.get('deadline', '').strip()
        assigned_to_name = request.form.get('assigned_to', '').strip()

        if not title:
            flash('Task title is required', 'error')
        else:
            # Find assignee user (optional)
            assignee = None
            if assigned_to_name:
                assignee = User.query.filter_by(username=assigned_to_name).first()
                if not assignee:
                    flash('Assigned user not found; leaving unassigned.', 'warning')

            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                except ValueError:
                    flash('Invalid date format (use YYYY-MM-DD)', 'error')

            task = Task(
                title=title,
                description=description,
                deadline=deadline,
                project=project,
                assignee=assignee
            )
            db.session.add(task)
            db.session.commit()
            flash('Task created!', 'success')

    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.deadline.asc()).all()
    users = User.query.all()

    return render_template('dashboard.html', tasks=tasks, users=users)


@app.route('/task/<int:task_id>/status/<string:new_status>', methods=['POST'])
@login_required
def change_task_status(task_id, new_status):
    task = Task.query.get_or_404(task_id)
    if new_status not in ['todo', 'doing', 'done']:
        flash('Invalid status', 'error')
    else:
        task.status = new_status
        db.session.commit()
        flash('Task updated!', 'success')

    return redirect(url_for('dashboard'))


@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0",debug=True)
