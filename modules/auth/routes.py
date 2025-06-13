from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app import db # Importa a instância do SQLAlchemy
from modules.auth.models import User # Importa o modelo User
from werkzeug.security import check_password_hash, generate_password_hash # Para hashing de senhas

auth = Blueprint('auth', __name__) # Cria o Blueprint 'auth'

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home')) # Redireciona para home se já logado

    if request.method == 'POST':
        matricula = request.form.get('matricula')
        password = request.form.get('password')

        user = User.query.filter_by(matricula=matricula).first()

        if not user or not user.check_password(password):
            flash('Matrícula ou senha incorretos. Tente novamente.', 'danger') # 'danger' para CSS
            return render_template('login.html')
        else:
            login_user(user)
            flash('Login realizado com sucesso!', 'success') # 'success' para CSS
            return redirect(url_for('home')) # Redireciona para o dashboard ou home

    return render_template('login.html')

@auth.route('/logout')
@login_required # Garante que apenas usuários logados podem fazer logout
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login')) # Redireciona para a página de login