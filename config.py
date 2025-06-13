import os

class Config:
    # Chave secreta para segurança das sessões Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sua_chave_secreta_muito_segura_aqui_para_dev'

    # Configuração do banco de dados SQLite (para começar)
    # Altere para PostgreSQL ou MySQL depois, se desejar
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configurações de e-mail (exemplo - Flask-Mail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')