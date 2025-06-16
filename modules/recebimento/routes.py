from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db, mail
from modules.core.models import Movimentacao, Fornecedor, ConfiguracaoEmail
from modules.auth.models import User
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta # Importe timedelta aqui
import re
from flask_mail import Message

recebimento = Blueprint('recebimento', __name__)

def extract_danfe_data(chave_acesso_input):
    if not chave_acesso_input or not isinstance(chave_acesso_input, str) or not chave_acesso_input.strip():
        return None, None, None # Retorna também data_emissao_simulada

    chave_acesso_input = chave_acesso_input.strip()

    if not chave_acesso_input.isdigit() or len(chave_acesso_input) != 44:
        return None, None, None # Retorna também data_emissao_simulada

    numero_danfe_simulado = chave_acesso_input[20:29] # Simulação do número da nota
    
    # Extrai Ano e Mês da Chave de Acesso (posições 2-3 para ano, 4-5 para mês)
    # Ex: Chave Acesso: CC AAMMDD NNNN EEEE XXXXXXXX PPPP VVVV DDDDDDDD V
    #                     ^ ^
    #                    Ano Mes
    try:
        ano = int(chave_acesso_input[2:4]) # Ano (ex: 24 para 2024)
        mes = int(chave_acesso_input[4:6]) # Mês (ex: 05 para Maio)
        # Assumindo século 21
        ano_completo = 2000 + ano
        # Para a simulação, vamos usar o dia 1 do mês. O dia não está na chave.
        data_emissao_simulada = datetime(ano_completo, mes, 1).date()
    except (ValueError, IndexError):
        data_emissao_simulada = None # Não foi possível extrair a data

    return numero_danfe_simulado, chave_acesso_input, data_emissao_simulada

def nota_fiscal_excedeu_5_dias(data_emissao):
    """
    Verifica se a data de emissão da nota fiscal excedeu 5 dias em relação à data atual.
    Recebe um objeto date.
    """
    if not data_emissao:
        return False
    hoje = datetime.now().date()
    diferenca = hoje - data_emissao
    return diferenca > timedelta(days=5)

def get_fornecedor_info_from_chave(chave_acesso):
    if chave_acesso and len(chave_acesso) == 44 and chave_acesso.isdigit():
        cnpj_numeros = chave_acesso[6:20]
        cnpj_formatado = f"{cnpj_numeros[0:2]}.{cnpj_numeros[2:5]}.{cnpj_numeros[5:8]}/{cnpj_numeros[8:12]}-{cnpj_numeros[12:14]}"
        nome_fornecedor_simulado = f"Fornecedor DANFE {cnpj_numeros[0:4]} (Simulado)"
        return {
            'cnpj': cnpj_formatado,
            'nome': nome_fornecedor_simulado,
            'codigo_fornecedor': f"CF-{cnpj_numeros[0:8]}" 
        }
    return None

def send_alerta_atraso_email(nota_info):
    config_email = ConfiguracaoEmail.query.filter_by(tipo_email='recebimento_atraso_gestor').first()
    if not config_email:
        print("Aviso: Configuração de e-mail de alerta de atraso para gestores não encontrada.")
        return

    assunto = config_email.assunto
    corpo_template = config_email.corpo_template

    corpo_formatado = corpo_template.replace('{numero_danfe}', nota_info['numero_danfe']) \
                                   .replace('{chave_acesso}', nota_info['chave_acesso']) \
                                   .replace('{data_emissao}', nota_info['data_emissao'].strftime('%d/%m/%Y')) \
                                   .replace('{fornecedor_nome}', nota_info['fornecedor_nome']) \
                                   .replace('{data_recebimento}', nota_info['data_recebimento'].strftime('%d/%m/%Y %H:%M:%S')) \
                                   .replace('{dias_atraso}', str(nota_info['dias_atraso']))

    gestores_emails = [user.email for user in User.query.filter_by(tipo_usuario='Gestor').all()]
    
    # Adicionar destinatários adicionais do campo configurado
    destinatarios_adicionais = []
    if config_email.destinatarios_adicionais:
        destinatarios_adicionais = [email.strip() for email in config_email.destinatarios_adicionais.split(',') if email.strip()]
    
    all_recipients = list(set(gestores_emails + destinatarios_adicionais)) # Remove duplicatas

    if not all_recipients:
        print("Aviso: Nenhum destinatário configurado para enviar e-mail de alerta de atraso.")
        return

    try:
        mail_instance = current_app.extensions.get('mail')
        if mail_instance:
            msg = Message(assunto, recipients=all_recipients)
            msg.body = corpo_formatado
            mail_instance.send(msg)
            print(f"E-mail de alerta de atraso enviado para: {', '.join(all_recipients)}")
        else:
            print("Erro: A extensão 'mail' não está configurada ou acessível.")
    except Exception as e:
        print(f"Erro ao enviar e-mail de alerta de atraso: {str(e)}")


def send_recebimento_email(movimentacoes_list):
    email_config = ConfiguracaoEmail.query.filter_by(tipo_email='recebimento_gestor').first()
    if not email_config:
        print("Aviso: Configuração de e-mail de recebimento para gestores não encontrada.")
        flash("Aviso: Configuração de e-mail para gestores não encontrada. E-mail não enviado.", "warning")
        return

    assunto = email_config.assunto
    corpo_template = email_config.corpo_template

    email_body_notes = []
    for mov in movimentacoes_list:
        fornecedor_nome = mov.fornecedor.nome if mov.fornecedor else 'N/A'
        email_body_notes.append(
            f"- NF: {mov.numero_danfe}, Chave: {mov.chave_acesso}, Fornecedor: {fornecedor_nome}"
        )
    
    first_mov = movimentacoes_list[0]
    operador_nome = first_mov.operador.nome_completo if first_mov.operador else 'N/A'
    matricula_operador = first_mov.matricula_operador
    data_hora_lote = first_mov.data_movimentacao.strftime('%d/%m/%Y %H:%M:%S')

    corpo_formatado = corpo_template.replace('[TIPO_EMAIL]', 'Recebimento de Peças (Lote)') \
                                   .replace('{nota}', ', '.join([m.numero_danfe for m in movimentacoes_list])) \
                                   .replace('{chave}', '\n'.join([m.chave_acesso for m in movimentacoes_list])) \
                                   .replace('{fornecedor}', 'Múltiplos Fornecedores' if len(set(m.fornecedor.nome for m in movimentacoes_list)) > 1 else (movimentacoes_list[0].fornecedor.nome if movimentacoes_list[0].fornecedor else 'N/A')) \
                                   .replace('{operador}', operador_nome) \
                                   .replace('{matricula_operador}', matricula_operador) \
                                   .replace('{responsavel}', first_mov.responsavel.nome_completo if first_mov.responsavel else 'N/A') \
                                   .replace('{data_hora}', data_hora_lote) \
                                   .replace('{id_processa}', 'N/A (Recebimento)')

    corpo_formatado = corpo_formatado.replace('Detalhes:', 'Notas Processadas:\n' + '\n'.join(email_body_notes) + '\nDetalhes do Lote:')


    gestores_emails = [user.email for user in User.query.filter_by(tipo_usuario='Gestor').all()]
    
    # Adicionar destinatários adicionais do campo configurado
    destinatarios_adicionais = []
    if email_config.destinatarios_adicionais:
        destinatarios_adicionais = [email.strip() for email in email_config.destinatarios_adicionais.split(',') if email.strip()]
    
    all_recipients = list(set(gestores_emails + destinatarios_adicionais)) # Remove duplicatas

    if not all_recipients:
        print("Aviso: Nenhum destinatário configurado para enviar e-mail de recebimento de lote.")
        flash("Aviso: Nenhum destinatário configurado para enviar e-mail de recebimento de lote.", "warning")
        return

    try:
        mail_instance = current_app.extensions.get('mail')
        if mail_instance:
            msg = Message(assunto, recipients=all_recipients)
            msg.body = corpo_formatado
            mail_instance.send(msg)
            print(f"E-mail de recebimento de lote enviado para: {', '.join(all_recipients)}")
        else:
            print("Erro: A extensão 'mail' não está configurada ou acessível.")
    except Exception as e:
        print(f"Erro ao enviar e-mail de recebimento de lote: {str(e)}")
        flash(f"Erro ao enviar e-mail de recebimento de lote: {str(e)}", "warning")


@recebimento.route('/recebimento', methods=['GET', 'POST'])
@login_required
def recebimento_pecas():
    allowed_roles = ['Gestor', 'LSL', 'DLI', 'PQM']
    if not current_user.tipo_usuario in allowed_roles:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    responsaveis = User.query.filter(User.tipo_usuario.in_(['DLI', 'PQM'])).all()

    if request.method == 'POST':
        chaves_acesso_input = request.form.get('chaves_acesso')
        matricula_operador = current_user.matricula
        turno_operador = current_user.turno
        responsavel_id = request.form.get('responsavel_id')

        if not chaves_acesso_input:
            flash('Nenhuma chave de acesso foi informada para o recebimento.', 'danger')
            return render_template('recebimento/recebimento.html', responsaveis=responsaveis)

        chaves = [c.strip() for c in chaves_acesso_input.splitlines() if c.strip()]
        
        if not chaves:
            flash('Nenhuma chave de acesso válida encontrada após processamento da entrada.', 'danger')
            return render_template('recebimento/recebimento.html', responsaveis=responsaveis)

        process_results = []
        emails_to_send_data = [] # Para coletar dados das notas para o e-mail
        alert_emails_to_send_data = [] # Para coletar dados para o alerta de 5 dias

        for chave_acesso in chaves:
            numero_danfe, chave_acesso_validada, data_emissao_simulada = extract_danfe_data(chave_acesso)

            if not chave_acesso_validada:
                process_results.append({'chave': chave_acesso, 'status': 'Falha', 'mensagem': 'Chave de Acesso inválida ou com formato incorreto.'})
                continue

            movimentacao_existente = Movimentacao.query.filter_by(chave_acesso=chave_acesso_validada).first()
            if movimentacao_existente:
                process_results.append({'chave': chave_acesso_validada, 'status': 'Ignorada', 'mensagem': 'DANFE já registrada como Recebimento.'})
                continue

            fornecedor_info = get_fornecedor_info_from_chave(chave_acesso_validada)
            fornecedor = None

            if fornecedor_info:
                fornecedor = Fornecedor.query.filter_by(cnpj=fornecedor_info['cnpj']).first()
                if not fornecedor:
                    try:
                        fornecedor = Fornecedor(
                            codigo_fornecedor=fornecedor_info['codigo_fornecedor'],
                            nome=fornecedor_info['nome'],
                            cnpj=fornecedor_info['cnpj']
                        )
                        db.session.add(fornecedor)
                        db.session.commit()
                        flash(f'Fornecedor "{fornecedor.nome}" cadastrado automaticamente (Chave: {chave_acesso_validada[-6:]}).', 'info')
                    except IntegrityError:
                        db.session.rollback()
                        fornecedor = Fornecedor.query.filter_by(cnpj=fornecedor_info['cnpj']).first()
                    except Exception as e:
                        process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': f'Erro ao cadastrar fornecedor: {str(e)}'})
                        continue
                
                if not fornecedor:
                    process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': 'Não foi possível identificar/cadastrar o fornecedor.'})
                    continue

            try:
                nova_movimentacao = Movimentacao(
                    tipo_movimentacao='Recebimento',
                    numero_danfe=numero_danfe,
                    chave_acesso=chave_acesso_validada,
                    fornecedor_id=fornecedor.id,
                    matricula_operador=matricula_operador,
                    turno=turno_operador,
                    responsavel_id=responsavel_id,
                    status='Pendente',
                    data_movimentacao=datetime.now() # Data e hora do recebimento
                )
                db.session.add(nova_movimentacao)
                db.session.commit()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Sucesso', 'mensagem': 'Recebimento registrado.'})
                emails_to_send_data.append(nova_movimentacao)

                # Lógica de alerta de 5 dias
                if data_emissao_simulada:
                    if nota_fiscal_excedeu_5_dias(data_emissao_simulada):
                        dias_atraso = (datetime.now().date() - data_emissao_simulada).days
                        flash(f'AVISO: A DANFE {numero_danfe} (Chave: {chave_acesso_validada[-6:]}) excedeu {dias_atraso} dias da emissão!', 'warning')
                        alert_emails_to_send_data.append({
                            'numero_danfe': numero_danfe,
                            'chave_acesso': chave_acesso_validada,
                            'data_emissao': data_emissao_simulada,
                            'fornecedor_nome': fornecedor.nome,
                            'data_recebimento': nova_movimentacao.data_movimentacao,
                            'dias_atraso': dias_atraso
                        })

            except Exception as e:
                db.session.rollback()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': f'Erro ao registrar movimentação: {str(e)}'})
        
        if emails_to_send_data:
            send_recebimento_email(emails_to_send_data)
        
        if alert_emails_to_send_data:
            for alerta_info in alert_emails_to_send_data:
                send_alerta_atraso_email(alerta_info)

        success_count = sum(1 for r in process_results if r['status'] == 'Sucesso')
        flash(f'Processamento do lote concluído. {success_count} nota(s) recebida(s) com sucesso.', 'info')
        
        return render_template('recebimento/recebimento.html', 
                               responsaveis=responsaveis, 
                               process_results=process_results)

    return render_template('recebimento/recebimento.html', responsaveis=responsaveis)