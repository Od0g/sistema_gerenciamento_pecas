from app import db, login_manager # Importe 'db' e 'login_manager' do app.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Função que o Flask-Login usa para carregar um usuário
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'Usuarios' # Define o nome da tabela no BD

    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(255), nullable=False)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    turno = db.Column(db.String(20), nullable=False)
    numero_cracha = db.Column(db.String(50))
    tipo_usuario = db.Column(db.Enum('Gestor', 'LSL', 'DLI', 'PQM'), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=db.func.current_timestamp())
    email = db.Column(db.String(255), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.senha_hash, password)

    def __repr__(self):
        return f'<User {self.matricula}>'