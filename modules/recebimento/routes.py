# modules/recebimento/routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db, mail
from modules.core.models import Movimentacao, Fornecedor
from modules.auth.models import User
from sqlalchemy.exc import IntegrityError
import datetime
import re
from flask_mail import Message
from modules.core.models import ConfiguracaoEmail

recebimento = Blueprint('recebimento', __name__)

def extract_danfe_data(chave_acesso_input):
    if not chave_acesso_input or not chave_acesso_input.isdigit() or len(chave_acesso_input) != 44:
        return None, None
    numero_danfe_simulado = chave_acesso_input[20:29]
    return numero_danfe_simulado, chave_acesso_input

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
        emails_to_send_data = []

        for chave_acesso in chaves: # <<< O LOOP ESTÁ AQUI
            # danfe_data = extract_danfe_data(danfe_input) # <<< REMOVA OU COMENTE ESSA LINHA SE AINDA TIVER
            numero_danfe, chave_acesso_validada = extract_danfe_data(chave_acesso) # <<< ESTA LINHA É A CORRETA DENTRO DO LOOP

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
                    data_movimentacao=datetime.datetime.now()
                )
                db.session.add(nova_movimentacao)
                db.session.commit()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Sucesso', 'mensagem': 'Recebimento registrado.'})
                emails_to_send_data.append(nova_movimentacao)

            except Exception as e:
                db.session.rollback()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': f'Erro ao registrar movimentação: {str(e)}'})

        if emails_to_send_data:
            send_recebimento_email(emails_to_send_data)

        success_count = sum(1 for r in process_results if r['status'] == 'Sucesso')
        flash(f'Processamento do lote concluído. {success_count} nota(s) recebida(s) com sucesso.', 'info')

        return render_template('recebimento/recebimento.html', 
                               responsaveis=responsaveis, 
                               process_results=process_results)

    return render_template('recebimento/recebimento.html', responsaveis=responsaveis)


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

    if not gestores_emails:
        print("Aviso: Nenhum gestor encontrado para enviar e-mail de recebimento de lote.")
        flash("Aviso: Nenhum gestor encontrado para enviar e-mail de recebimento de lote.", "warning")
        return

    try:
        msg = Message(assunto, recipients=gestores_emails)
        msg.body = corpo_formatado
        mail.send(msg)
        print(f"E-mail de recebimento de lote enviado para: {', '.join(gestores_emails)}")
    except Exception as e:
        print(f"Erro ao enviar e-mail de recebimento de lote: {str(e)}")
        flash(f"Erro ao enviar e-mail de recebimento de lote: {str(e)}", "warning")