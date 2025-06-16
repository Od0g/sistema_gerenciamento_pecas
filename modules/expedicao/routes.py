from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app # <<< ADICIONE current_app AQUI
from flask_login import login_required, current_user
from app import db, mail # Importa a instância do SQLAlchemy e Flask-Mail
from modules.core.models import Movimentacao, Fornecedor, ConfiguracaoEmail # Importa os modelos
from modules.auth.models import User # Para buscar usuários
import datetime
import re
from flask_mail import Message

expedicao = Blueprint('expedicao', __name__)

# Reutiliza a função de extração de DANFE (para consistência)
def extract_danfe_data(chave_acesso_input):
    if not chave_acesso_input or not chave_acesso_input.isdigit() or len(chave_acesso_input) != 44:
        return None, None # Chave inválida

    # Simulação: número da nota
    numero_danfe_simulado = chave_acesso_input[20:29] # Ex: os 9 dígitos do meio
    return numero_danfe_simulado, chave_acesso_input

# Reutiliza a função de obtenção de info do fornecedor (para consistência)
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

@expedicao.route('/expedicao', methods=['GET', 'POST'])
@login_required
def expedicao_pecas():
    allowed_roles = ['Gestor', 'LSL', 'DLI', 'PQM']
    if not current_user.tipo_usuario in allowed_roles:
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        chaves_acesso_input = request.form.get('chaves_acesso')
        matricula_operador = current_user.matricula
        turno_operador = current_user.turno
        id_processa = request.form.get('id_processa') # ID do Processa para todas as notas do lote

        if not chaves_acesso_input:
            flash('Nenhuma chave de acesso foi informada para a expedição.', 'danger')
            return render_template('expedicao/expedicao.html')

        if not id_processa:
            flash('ID do Processa (ERP) é obrigatório para Expedição.', 'danger')
            return render_template('expedicao/expedicao.html')

        chaves = [c.strip() for c in chaves_acesso_input.splitlines() if c.strip()]
        
        if not chaves:
            flash('Nenhuma chave de acesso válida encontrada após processamento da entrada.', 'danger')
            return render_template('expedicao/expedicao.html')

        process_results = []
        emails_to_send_data = [] # Para coletar dados das notas para o e-mail

        for chave_acesso in chaves:
            numero_danfe, chave_acesso_validada = extract_danfe_data(chave_acesso)

            if not chave_acesso_validada:
                process_results.append({'chave': chave_acesso, 'status': 'Falha', 'mensagem': 'Chave de Acesso inválida ou com formato incorreto.'})
                continue

            movimentacao = Movimentacao.query.filter_by(chave_acesso=chave_acesso_validada).first()

            if not movimentacao:
                process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': 'DANFE não encontrada como "Recebida" no sistema.'})
                continue # Pula para a próxima chave

            if movimentacao.status == 'Concluido' and movimentacao.tipo_movimentacao == 'Expedicao':
                process_results.append({'chave': chave_acesso_validada, 'status': 'Ignorada', 'mensagem': 'DANFE já registrada como Expedição e Concluída.'})
                continue

            # Opcional: Se o fornecedor não foi vinculado ao recebimento, tente vincular agora.
            if not movimentacao.fornecedor:
                fornecedor_info = get_fornecedor_info_from_chave(chave_acesso_validada)
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
                        except Exception as e:
                            print(f"Erro ao cadastrar fornecedor na expedição (aviso): {str(e)}")
                            # Apenas loga, não impede a expedição se o fornecedor for o mesmo da chave
                    if fornecedor:
                        movimentacao.fornecedor_id = fornecedor.id
                        db.session.add(movimentacao)


            # Atualizar Movimentação para Expedição
            try:
                movimentacao.tipo_movimentacao = 'Expedicao'
                movimentacao.id_processa = id_processa
                movimentacao.matricula_operador = matricula_operador
                movimentacao.turno = turno_operador
                movimentacao.data_movimentacao = datetime.datetime.now()
                movimentacao.status = 'Concluido'

                db.session.commit()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Sucesso', 'mensagem': 'Expedição registrada.'})
                emails_to_send_data.append(movimentacao)

            except Exception as e:
                db.session.rollback()
                process_results.append({'chave': chave_acesso_validada, 'status': 'Falha', 'mensagem': f'Erro ao registrar expedição: {str(e)}'})
        
        # Enviar e-mail após processar todas as notas no lote
        if emails_to_send_data:
            send_expedicao_email(emails_to_send_data, id_processa)
        
        # Flash message consolidada para o lote
        success_count = sum(1 for r in process_results if r['status'] == 'Sucesso')
        flash(f'Processamento do lote concluído. {success_count} nota(s) expedida(s) com sucesso.', 'info')
        
        return render_template('expedicao/expedicao.html', 
                               process_results=process_results)

    return render_template('expedicao/expedicao.html')


def send_expedicao_email(movimentacoes_list, id_processa):
    email_config = ConfiguracaoEmail.query.filter_by(tipo_email='expedicao_gestor').first()
    if not email_config:
        print("Aviso: Configuração de e-mail de expedição para gestores não encontrada.")
        flash("Aviso: Configuração de e-mail para gestores não encontrada. E-mail não enviado.", "warning")
        return

    assunto = email_config.assunto
    corpo_template = email_config.corpo_template

    email_body_notes = []
    for mov in movimentacoes_list:
        fornecedor_nome = mov.fornecedor.nome if mov.fornecedor else 'N/A'
        email_body_notes.append(
            f"- NF: {mov.numero_danfe}, Chave: {mov.chave_acesso}, Fornecedor: {fornecedor_nome}, ID Processa: {mov.id_processa if mov.id_processa else 'N/A'}"
        )
    
    first_mov = movimentacoes_list[0]
    operador_nome = first_mov.operador.nome_completo if first_mov.operador else 'N/A'
    matricula_operador = first_mov.matricula_operador
    data_hora_lote = first_mov.data_movimentacao.strftime('%d/%m/%Y %H:%M:%S')

    corpo_formatado = corpo_template.replace('[TIPO_EMAIL]', 'Expedição de Peças (Lote)') \
                                   .replace('{nota}', ', '.join([m.numero_danfe for m in movimentacoes_list])) \
                                   .replace('{chave}', '\n'.join([m.chave_acesso for m in movimentacoes_list])) \
                                   .replace('{fornecedor}', 'Múltiplos Fornecedores' if len(set(m.fornecedor.nome for m in movimentacoes_list)) > 1 else (movimentacoes_list[0].fornecedor.nome if movimentacoes_list[0].fornecedor else 'N/A')) \
                                   .replace('{operador}', operador_nome) \
                                   .replace('{matricula_operador}', matricula_operador) \
                                   .replace('{id_processa}', id_processa) \
                                   .replace('{data_hora}', data_hora_lote) \
                                   .replace('{responsavel}', 'N/A (Expedição)')

    corpo_formatado = corpo_formatado.replace('Detalhes:', 'Notas Processadas:\n' + '\n'.join(email_body_notes) + '\nDetalhes do Lote:')


    gestores_emails = [user.email for user in User.query.filter_by(tipo_usuario='Gestor').all()]
    
    # Adicionar destinatários adicionais do campo configurado
    destinatarios_adicionais = []
    if email_config.destinatarios_adicionais:
        destinatarios_adicionais = [email.strip() for email in email_config.destinatarios_adicionais.split(',') if email.strip()]
    
    all_recipients = list(set(gestores_emails + destinatarios_adicionais)) # Remove duplicatas

    if not all_recipients:
        print("Aviso: Nenhum destinatário configurado para enviar e-mail de expedição de lote.")
        flash("Aviso: Nenhum destinatário configurado para enviar e-mail de expedição de lote.", "warning")
        return

    try:
        mail_instance = current_app.extensions.get('mail') # Acessa a instância do Flask-Mail corretamente
        if mail_instance:
            msg = Message(assunto, recipients=all_recipients)
            msg.body = corpo_formatado
            mail_instance.send(msg)
            print(f"E-mail de expedição de lote enviado para: {', '.join(all_recipients)}")
        else:
            print("Erro: A extensão 'mail' não está configurada ou acessível.")
    except Exception as e:
        print(f"Erro ao enviar e-mail de expedição de lote: {str(e)}")
        flash(f"Erro ao enviar e-mail de expedição de lote: {str(e)}", "warning")
