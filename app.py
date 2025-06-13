from flask import Flask, render_template, request
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
import datetime
from flask_mail import Mail # <--- Adicione esta importação

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail() # <--- Inicialize a instância do Mail aqui

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app) # <--- Inicialize o Mail com o aplicativo aqui

    @app.context_processor
    def inject_global_vars():
        return {
            'current_year': datetime.datetime.now().year
        }

    # Importe e registre os blueprints aqui
    from modules.auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/')

    from modules.cadastro.routes import cadastro as cadastro_blueprint
    app.register_blueprint(cadastro_blueprint, url_prefix='/')

    # NOVO: Importar e registrar o Blueprint de Recebimento
    from modules.recebimento.routes import recebimento as recebimento_blueprint # <--- ADICIONE ESTA LINHA
    app.register_blueprint(recebimento_blueprint, url_prefix='/') # <--- ADICIONE ESTA LINHA

    # NOVO: Importar e registrar o Blueprint de Expedição
    from modules.expedicao.routes import expedicao as expedicao_blueprint # <--- ADICIONE ESTA LINHA
    app.register_blueprint(expedicao_blueprint, url_prefix='/') # <--- ADICIONE ESTA LINHA

    # NOVO: Importar e registrar o Blueprint de Relatórios
    from modules.relatorios.routes import relatorios as relatorios_blueprint # <--- ADICIONE ESTA LINHA
    app.register_blueprint(relatorios_blueprint, url_prefix='/') # <--- ADICIONE ESTA LINHA

    # Importar os modelos para que db.create_all() os reconheça
    from modules.auth.models import User
    from modules.core.models import Fornecedor, Movimentacao, ConfiguracaoEmail

    # Rota raiz (Home/Dashboard)
    @app.route('/')
    @login_required
    def home():
        return render_template('dashboard.html')

    with app.app_context():
        db.create_all()

        # Adicione este bloco para criar um usuário inicial para teste
        # ATENÇÃO: REMOVA ISSO EM PRODUÇÃO!
        if not User.query.filter_by(matricula='admin').first():
            admin_user = User(
                nome_completo='Administrador Teste',
                matricula='admin',
                turno='Geral',
                tipo_usuario='Gestor',
                email='admin@sistema.com'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Usuário 'admin' criado com sucesso!")

        # Opcional: Adicione um fornecedor de teste se ainda não tiver um
        if not Fornecedor.query.filter_by(cnpj='00.000.000/0001-00').first():
            test_fornecedor = Fornecedor(
                codigo_fornecedor='F001',
                nome='Fornecedor Teste LTDA',
                cnpj='00.000.000/0001-00'
            )
            db.session.add(test_fornecedor)
            db.session.commit()
            print("Fornecedor 'Fornecedor Teste LTDA' criado com sucesso!")


    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)