from flask import Flask, render_template, request
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
import datetime
from flask_mail import Mail
from flask_apscheduler import APScheduler # <<< Nova Importação

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
scheduler = APScheduler() # <<< Nova Inicialização

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Configurações para o APScheduler (exemplo)
    app.config['SCHEDULER_API_ENABLED'] = True # Opcional: para acessar o scheduler via API
    # scheduler.init_app(app) # Inicializa o scheduler com o app
    # scheduler.start() # Inicia o scheduler
    # ATENÇÃO: Se for usar o scheduler, você precisará de uma forma de executá-lo em segundo plano,
    # ou usar um WSGI server como Gunicorn que pode lidar com isso.
    # Para testes iniciais, vamos chamar a função de verificação ao iniciar o app,
    # e você pode agendar mais tarde.

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)

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

    from modules.recebimento.routes import recebimento as recebimento_blueprint
    app.register_blueprint(recebimento_blueprint, url_prefix='/')

    from modules.expedicao.routes import expedicao as expedicao_blueprint
    app.register_blueprint(expedicao_blueprint, url_prefix='/')

    from modules.relatorios.routes import relatorios as relatorios_blueprint
    app.register_blueprint(relatorios_blueprint, url_prefix='/')

    # Importar os modelos para que db.create_all() os reconheça
    from modules.auth.models import User
    from modules.core.models import Fornecedor, Movimentacao, ConfiguracaoEmail

    # IMPORTAR A FUNÇÃO DE VERIFICAÇÃO PARA O SCHEDULER
    from modules.recebimento.routes import send_alerta_atraso_email # Reutilizar função de alerta
    from modules.core.models import ConfiguracaoEmail # Importar se não estiver em escopo

    # Rota raiz (Home/Dashboard)
    @app.route('/')
    @login_required
    def home():
        return render_template('dashboard.html')

    with app.app_context():
        db.create_all()

        # Adicione este bloco para criar um usuário inicial para teste
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

        if not Fornecedor.query.filter_by(cnpj='00.000.000/0001-00').first():
            test_fornecedor = Fornecedor(
                codigo_fornecedor='F001',
                nome='Fornecedor Teste LTDA',
                cnpj='00.000.000/0001-00'
            )
            db.session.add(test_fornecedor)
            db.session.commit()
            print("Fornecedor 'Fornecedor Teste LTDA' criado com sucesso!")

        # === FUNÇÃO AGENDADA PARA VERIFICAR NOTAS ATRASADAS ===
        def verificar_notas_atrasadas_agendado():
            with app.app_context(): # Precisa do contexto da aplicação para acessar o DB
                print(f"[{datetime.now()}] Verificando notas com mais de 5 dias...")
                hoje = datetime.now().date()
                limite_dias = timedelta(days=5)

                # Busca todas as movimentações de Recebimento que ainda estão Pendentes
                # e que têm uma chave de acesso (para tentar extrair a data de emissão simulada)
                notas_para_verificar = Movimentacao.query.filter(
                    Movimentacao.status == 'Pendente',
                    Movimentacao.tipo_movimentacao == 'Recebimento'
                ).all()

                atrasos_encontrados = []

                for mov in notas_para_verificar:
                    # Tenta extrair a data de emissão simulada da chave de acesso
                    # A função extract_danfe_data não está importada aqui diretamente.
                    # Para simplificar, vamos replicar a lógica necessária ou criar uma função mais genérica
                    # em modules/core/utils.py que extraia data.
                    # Por enquanto, vamos fazer uma verificação simulada, pois a data de emissão real não está no BD.
                    # Se você precisar que o ALERTA seja sobre notas *RECEBIDAS* há mais de 5 dias, o cálculo muda.
                    # O requisito inicial é "nota *exceder o período de 5 dias* [da sua data de] emissão".
                    # Como não salvamos 'data_emissao' no BD, vamos usar 'data_movimentacao' (recebimento)
                    # como proxy, e alertar se o recebimento foi há mais de 5 dias e a nota ainda está pendente.
                    
                    if mov.data_movimentacao and (hoje - mov.data_movimentacao.date()) > limite_dias:
                        dias_atraso_recebimento = (hoje - mov.data_movimentacao.date()).days
                        fornecedor_nome = mov.fornecedor.nome if mov.fornecedor else 'N/A'
                        
                        alerta_info = {
                            'numero_danfe': mov.numero_danfe,
                            'chave_acesso': mov.chave_acesso,
                            'data_emissao': mov.data_movimentacao.date(), # Usando data de recebimento como proxy
                            'fornecedor_nome': fornecedor_nome,
                            'data_recebimento': mov.data_movimentacao,
                            'dias_atraso': dias_atraso_recebimento
                        }
                        atrasos_encontrados.append(alerta_info)

                if atrasos_encontrados:
                    # Envia um e-mail consolidado para todos os atrasos encontrados
                    send_alerta_atraso_email_lote(atrasos_encontrados) # Nova função para envio de lote de alertas
                else:
                    print(f"[{datetime.now()}] Nenhuma nota com mais de 5 dias de recebimento pendente encontrada.")
        # === FIM DA FUNÇÃO AGENDADA ===

        # Configurar o scheduler APENAS UMA VEZ
        if not scheduler.running:
            scheduler.init_app(app)
            scheduler.start()
            # Adicionar a tarefa agendada: diário à 00:00 (meia-noite)
            # Ou a cada 5 minutos para teste:
            # scheduler.add_job(id='daily_alert_check', func=verificar_notas_atrasadas_agendado, trigger='interval', minutes=5)
            # Para produção (diariamente à 00:00):
            scheduler.add_job(id='daily_alert_check', func=verificar_notas_atrasadas_agendado, trigger='cron', hour=0, minute=0)
            print("Scheduler iniciado e tarefa de alerta agendada.")

    return app

# Nova função para enviar um e-mail consolidado de alertas de atraso
def send_alerta_atraso_email_lote(notas_atrasadas_list):
    config_email = ConfiguracaoEmail.query.filter_by(tipo_email='alerta_atraso_diario_gestor').first()
    if not config_email:
        print("Aviso: Configuração de e-mail 'alerta_atraso_diario_gestor' não encontrada. E-mail não enviado.")
        return

    assunto = config_email.assunto
    corpo_template = config_email.corpo_template

    # Constrói a lista de detalhes das notas para o corpo do e-mail
    detalhes_notas_atrasadas = []
    for nota in notas_atrasadas_list:
        detalhes_notas_atrasadas.append(
            f"- NF: {nota['numero_danfe']}, Chave: {nota['chave_acesso']}, Emissão: {nota['data_emissao'].strftime('%d/%m/%Y')}, Fornecedor: {nota['fornecedor_nome']}, Recebimento: {nota['data_recebimento'].strftime('%d/%m/%Y %H:%M:%S')}, Dias Atraso: {nota['dias_atraso']}"
        )
    
    # Prepara o corpo do e-mail principal
    corpo_formatado = corpo_template.replace('[DETALHES_NOTAS]', '\n'.join(detalhes_notas_atrasadas))
    # Adicione outras variáveis se o template usar (ex: {data_hoje})
    corpo_formatado = corpo_formatado.replace('{data_hoje}', datetime.now().strftime('%d/%m/%Y'))

    gestores_emails = [user.email for user in User.query.filter_by(tipo_usuario='Gestor').all()]
    destinatarios_adicionais = []
    if config_email.destinatarios_adicionais:
        destinatarios_adicionais = [email.strip() for email in config_email.destinatarios_adicionais.split(',') if email.strip()]
    
    all_recipients = list(set(gestores_emails + destinatarios_adicionais))

    if not all_recipients:
        print("Aviso: Nenhum destinatário configurado para enviar e-mail de alerta de atraso diário.")
        return

    try:
        mail_instance = current_app.extensions.get('mail')
        if mail_instance:
            msg = Message(assunto, recipients=all_recipients)
            msg.body = corpo_formatado
            mail_instance.send(msg)
            print(f"E-mail de alerta de atraso diário enviado para: {', '.join(all_recipients)}")
        else:
            print("Erro: A extensão 'mail' não está configurada ou acessível.")
    except Exception as e:
        print(f"Erro ao enviar e-mail de alerta de atraso diário: {str(e)}")


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)