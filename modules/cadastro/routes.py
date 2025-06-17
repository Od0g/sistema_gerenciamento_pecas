from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db # Importa a instância do SQLAlchemy
from modules.auth.models import User # Para cadastrar e gerenciar usuários
from modules.core.models import Fornecedor, ConfiguracaoEmail, Movimentacao # Para outros cadastros
from werkzeug.security import generate_password_hash # Para hashing de senhas
from sqlalchemy.exc import IntegrityError # Para lidar com erros de unicidade

cadastro = Blueprint('cadastro', __name__)

# Função auxiliar para verificar permissão
def has_permission(user, allowed_roles):
    return user.is_authenticated and user.tipo_usuario in allowed_roles

@cadastro.route('/cadastro/usuarios', methods=['GET', 'POST'])
@login_required
def cadastro_usuarios():
    # Verifica se o usuário tem permissão (APENAS Gestor)
    if not has_permission(current_user, ['Gestor']): # <--- ALTERADO AQUI
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        nome_completo = request.form.get('nome_completo')
        matricula = request.form.get('matricula')
        turno = request.form.get('turno')
        numero_cracha = request.form.get('numero_cracha')
        tipo_usuario = request.form.get('tipo_usuario')
        email = request.form.get('email')
        senha = request.form.get('senha')

        # Validações básicas (você pode adicionar mais, como formato de e-mail, etc.)
        if not all([nome_completo, matricula, turno, tipo_usuario, email, senha]):
            flash('Todos os campos obrigatórios devem ser preenchidos.', 'danger')
            return render_template('cadastro/cadastro_usuarios.html', users=User.query.all())

        if User.query.filter_by(matricula=matricula).first():
            flash(f'Matrícula "{matricula}" já cadastrada.', 'danger')
            return render_template('cadastro/cadastro_usuarios.html', users=User.query.all())

        if User.query.filter_by(email=email).first():
            flash(f'E-mail "{email}" já cadastrado.', 'danger')
            return render_template('cadastro/cadastro_usuarios.html', users=User.query.all())

        try:
            new_user = User(
                nome_completo=nome_completo,
                matricula=matricula,
                turno=turno,
                numero_cracha=numero_cracha,
                tipo_usuario=tipo_usuario,
                email=email
            )
            new_user.set_password(senha) # Criptografa a senha
            db.session.add(new_user)
            db.session.commit()
            flash('Usuário cadastrado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar usuário: {str(e)}', 'danger')

        return redirect(url_for('cadastro.cadastro_usuarios')) # Redireciona para recarregar a lista

    users = User.query.all() # Busca todos os usuários para exibir na lista
    return render_template('cadastro/cadastro_usuarios.html', users=users)

# NOVA ROTA: Excluir Usuário
@cadastro.route('/cadastro/usuarios/excluir/<int:user_id>', methods=['POST'])
@login_required
def excluir_usuario(user_id):
    # Verifica se o usuário logado é um Gestor (apenas Gestores podem excluir outros usuários)
    if not has_permission(current_user, ['Gestor']):
        flash('Você não tem permissão para realizar esta operação.', 'danger')
        return redirect(url_for('home'))

    user_to_delete = User.query.get_or_404(user_id)

    # Prevenções de Segurança Cruciais:
    # 1. Impedir que um usuário exclua a si mesmo
    if user_to_delete.id == current_user.id:
        flash('Você não pode excluir sua própria conta!', 'danger')
        return redirect(url_for('cadastro.cadastro_usuarios'))

    # 2. Impedir exclusão do último Gestor (para evitar bloqueio do sistema)
    # Primeiro, conte quantos gestores existem
    num_gestores = User.query.filter_by(tipo_usuario='Gestor').count()
    if user_to_delete.tipo_usuario == 'Gestor' and num_gestores <= 1:
        flash('Não é possível excluir o último usuário Gestor. Crie outro Gestor primeiro, se necessário.', 'danger')
        return redirect(url_for('cadastro.cadastro_usuarios'))

    # 3. Verificar se o usuário tem movimentações vinculadas (opcional, mas boa prática)
    # Se um usuário tem registros de Movimentacao, excluí-lo pode quebrar o histórico
    # Decisão: permitir exclusão mesmo com movimentações, mas avisar ou considerar desativar em vez de excluir
    # Por enquanto, vamos permitir a exclusão, mas em sistemas reais, isso é um ponto de atenção.
    # Exemplo de verificação:
    # if Movimentacao.query.filter_by(matricula_operador=user_to_delete.matricula).first():
    #    flash('Não é possível excluir o usuário pois ele possui movimentações registradas. Considere desativá-lo.', 'danger')
    #    return redirect(url_for('cadastro.cadastro_usuarios'))

    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f'Usuário "{user_to_delete.nome_completo}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir usuário: {str(e)}', 'danger')

    return redirect(url_for('cadastro.cadastro_usuarios'))


@cadastro.route('/cadastro/fornecedores', methods=['GET', 'POST'])
@login_required
def cadastro_fornecedores():
    # Verifica se o usuário tem permissão (Gestor ou LSL)
    if not has_permission(current_user, ['Gestor', 'LSL']):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        codigo_fornecedor = request.form.get('codigo_fornecedor')
        nome = request.form.get('nome')
        cnpj = request.form.get('cnpj')

        if not all([codigo_fornecedor, nome, cnpj]):
            flash('Todos os campos obrigatórios devem ser preenchidos.', 'danger')
            return render_template('cadastro/cadastro_fornecedores.html', fornecedores=Fornecedor.query.all())

        if Fornecedor.query.filter_by(codigo_fornecedor=codigo_fornecedor).first():
            flash(f'Código de Fornecedor "{codigo_fornecedor}" já cadastrado.', 'danger')
            return render_template('cadastro/cadastro_fornecedores.html', fornecedores=Fornecedor.query.all())
        
        if Fornecedor.query.filter_by(cnpj=cnpj).first():
            flash(f'CNPJ "{cnpj}" já cadastrado.', 'danger')
            return render_template('cadastro/cadastro_fornecedores.html', fornecedores=Fornecedor.query.all())

        try:
            new_fornecedor = Fornecedor(
                codigo_fornecedor=codigo_fornecedor,
                nome=nome,
                cnpj=cnpj
            )
            db.session.add(new_fornecedor)
            db.session.commit()
            flash('Fornecedor cadastrado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar fornecedor: {str(e)}', 'danger')

        return redirect(url_for('cadastro.cadastro_fornecedores'))

    fornecedores = Fornecedor.query.all()
    return render_template('cadastro/cadastro_fornecedores.html', fornecedores=fornecedores)

# NOVA ROTA: Edição de Fornecedor
@cadastro.route('/cadastro/fornecedores/editar/<int:fornecedor_id>', methods=['GET', 'POST'])
@login_required
def editar_fornecedor(fornecedor_id):
    if not has_permission(current_user, ['Gestor', 'LSL']):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    fornecedor = Fornecedor.query.get_or_404(fornecedor_id)

    if request.method == 'POST':
        novo_codigo = request.form.get('codigo_fornecedor')
        novo_nome = request.form.get('nome')
        novo_cnpj = request.form.get('cnpj')

        # Validações de unicidade para código e CNPJ (ignorando o próprio fornecedor sendo editado)
        if Fornecedor.query.filter(Fornecedor.codigo_fornecedor == novo_codigo, Fornecedor.id != fornecedor_id).first():
            flash(f'Código de Fornecedor "{novo_codigo}" já está em uso por outro fornecedor.', 'danger')
            return render_template('cadastro/editar_fornecedor.html', fornecedor=fornecedor)
        
        if Fornecedor.query.filter(Fornecedor.cnpj == novo_cnpj, Fornecedor.id != fornecedor_id).first():
            flash(f'CNPJ "{novo_cnpj}" já está em uso por outro fornecedor.', 'danger')
            return render_template('cadastro/editar_fornecedor.html', fornecedor=fornecedor)

        try:
            fornecedor.codigo_fornecedor = novo_codigo
            fornecedor.nome = novo_nome
            fornecedor.cnpj = novo_cnpj
            db.session.commit()
            flash('Fornecedor atualizado com sucesso!', 'success')
            return redirect(url_for('cadastro.cadastro_fornecedores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar fornecedor: {str(e)}', 'danger')

    return render_template('cadastro/editar_fornecedor.html', fornecedor=fornecedor)

# NOVA ROTA: Excluir Fornecedor
@cadastro.route('/cadastro/fornecedores/excluir/<int:fornecedor_id>', methods=['POST'])
@login_required
def excluir_fornecedor(fornecedor_id):
    if not has_permission(current_user, ['Gestor', 'LSL']):
        flash('Você não tem permissão para realizar esta operação.', 'danger')
        return redirect(url_for('home'))

    fornecedor = Fornecedor.query.get_or_404(fornecedor_id)

    # Verifica se o fornecedor tem movimentações vinculadas
    if Movimentacao.query.filter_by(fornecedor_id=fornecedor_id).first():
        flash('Não é possível excluir o fornecedor pois ele possui movimentações registradas.', 'danger')
        return redirect(url_for('cadastro.cadastro_fornecedores'))

    try:
        db.session.delete(fornecedor)
        db.session.commit()
        flash('Fornecedor excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir fornecedor: {str(e)}', 'danger')

    return redirect(url_for('cadastro.cadastro_fornecedores'))

@cadastro.route('/cadastro/emails', methods=['GET', 'POST'])
@login_required
def configuracao_emails():
    if not has_permission(current_user, ['Gestor', 'LSL']):
        flash('Você não tem permissão para acessar esta página.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        tipo_email = request.form.get('tipo_email')
        assunto = request.form.get('assunto')
        corpo_template = request.form.get('corpo_template')
        destinatarios_adicionais = request.form.get('destinatarios_adicionais') # <<< PEGA NOVO CAMPO

        if not all([tipo_email, assunto, corpo_template]):
            flash('Todos os campos obrigatórios (Tipo, Assunto, Corpo) devem ser preenchidos.', 'danger') # Adicionado "obrigatórios"
            return render_template('cadastro/configuracao_emails.html', configs=ConfiguracaoEmail.query.all())

        config = ConfiguracaoEmail.query.filter_by(tipo_email=tipo_email).first()
        try:
            if config:
                config.assunto = assunto
                config.corpo_template = corpo_template
                config.destinatarios_adicionais = destinatarios_adicionais # <<< SALVA NOVO CAMPO
                flash(f'Configuração de e-mail "{tipo_email}" atualizada com sucesso!', 'success')
            else:
                new_config = ConfiguracaoEmail(
                    tipo_email=tipo_email,
                    assunto=assunto,
                    corpo_template=corpo_template,
                    destinatarios_adicionais=destinatarios_adicionais # <<< SALVA NOVO CAMPO
                )
                db.session.add(new_config)
                flash(f'Configuração de e-mail "{tipo_email}" adicionada com sucesso!', 'success')
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar configuração de e-mail: {str(e)}', 'danger')

        return redirect(url_for('cadastro.configuracao_emails'))
    
    configs = ConfiguracaoEmail.query.all()
    return render_template('cadastro/configuracao_emails.html', configs=configs)