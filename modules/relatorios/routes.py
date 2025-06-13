from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response
from flask_login import login_required, current_user
from app import db # Importa a instância do SQLAlchemy
from modules.core.models import Movimentacao, Fornecedor # Importa os modelos
import datetime
import csv
from io import StringIO
# Importações para PDF (precisará instalar ReportLab ou FPDF)
# from reportlab.lib.pagesizes import letter
# from reportlab.pdfgen import canvas
# from reportlab.lib.units import inch

relatorios = Blueprint('relatorios', __name__) # <<< ESTA LINHA É CRÍTICA E PRECISA ESTAR AQUI!

@relatorios.route('/relatorios', methods=['GET'])
@login_required
def relatorios_geral():
    # Filtros
    tipo_movimentacao_filtro = request.args.get('tipo', None)
    status_filtro = request.args.get('status', None)
    id_processa_filtro = request.args.get('id_processa', None)
    fornecedor_filtro = request.args.get('fornecedor', None) # Nome ou CNPJ
    matricula_operador_filtro = request.args.get('matricula_operador', None)
    turno_filtro = request.args.get('turno', None)
    data_inicio_filtro = request.args.get('data_inicio', None)
    data_fim_filtro = request.args.get('data_fim', None)

    query = Movimentacao.query

    if tipo_movimentacao_filtro and tipo_movimentacao_filtro != 'Geral':
        query = query.filter(Movimentacao.tipo_movimentacao == tipo_movimentacao_filtro)

    if status_filtro and status_filtro != 'Todos':
        query = query.filter(Movimentacao.status == status_filtro)

    if id_processa_filtro:
        query = query.filter(Movimentacao.id_processa.ilike(f'%{id_processa_filtro}%'))

    if fornecedor_filtro:
        # Busca por nome ou CNPJ do fornecedor
        query = query.join(Fornecedor).filter(
            (Fornecedor.nome.ilike(f'%{fornecedor_filtro}%')) | 
            (Fornecedor.cnpj.ilike(f'%{fornecedor_filtro}%'))
        )

    if matricula_operador_filtro:
        query = query.filter(Movimentacao.matricula_operador.ilike(f'%{matricula_operador_filtro}%'))

    if turno_filtro and turno_filtro != 'Todos':
        query = query.filter(Movimentacao.turno == turno_filtro)

    if data_inicio_filtro:
        try:
            data_inicio = datetime.datetime.strptime(data_inicio_filtro, '%Y-%m-%d')
            query = query.filter(Movimentacao.data_movimentacao >= data_inicio)
        except ValueError:
            flash('Formato de Data de Início inválido.', 'danger')

    if data_fim_filtro:
        try:
            data_fim = datetime.datetime.strptime(data_fim_filtro, '%Y-%m-%d') + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1) # Inclui o dia inteiro
            query = query.filter(Movimentacao.data_movimentacao <= data_fim)
        except ValueError:
            flash('Formato de Data de Fim inválido.', 'danger')

    movimentacoes = query.order_by(Movimentacao.data_movimentacao.desc()).all()
    fornecedores_existentes = Fornecedor.query.all()

    return render_template('relatorios/relatorios.html', 
                           movimentacoes=movimentacoes,
                           fornecedores_existentes=fornecedores_existentes,
                           current_filters=request.args # Passa os filtros atuais para o template
                           )

@relatorios.route('/relatorios/export/csv', methods=['GET'])
@login_required
def export_csv():
    # Replicar a lógica de filtro do relatorios_geral para aplicar na exportação
    tipo_movimentacao_filtro = request.args.get('tipo', None)
    status_filtro = request.args.get('status', None)
    id_processa_filtro = request.args.get('id_processa', None)
    fornecedor_filtro = request.args.get('fornecedor', None)
    matricula_operador_filtro = request.args.get('matricula_operador', None)
    turno_filtro = request.args.get('turno', None)
    data_inicio_filtro = request.args.get('data_inicio', None)
    data_fim_filtro = request.args.get('data_fim', None)

    query = Movimentacao.query

    if tipo_movimentacao_filtro and tipo_movimentacao_filtro != 'Geral':
        query = query.filter(Movimentacao.tipo_movimentacao == tipo_movimentacao_filtro)
    if status_filtro and status_filtro != 'Todos':
        query = query.filter(Movimentacao.status == status_filtro)
    if id_processa_filtro:
        query = query.filter(Movimentacao.id_processa.ilike(f'%{id_processa_filtro}%'))
    if fornecedor_filtro:
        query = query.join(Fornecedor).filter(
            (Fornecedor.nome.ilike(f'%{fornecedor_filtro}%')) | 
            (Fornecedor.cnpj.ilike(f'%{fornecedor_filtro}%'))
        )
    if matricula_operador_filtro:
        query = query.filter(Movimentacao.matricula_operador.ilike(f'%{matricula_operador_filtro}%'))
    if turno_filtro and turno_filtro != 'Todos':
        query = query.filter(Movimentacao.turno == turno_filtro)
    if data_inicio_filtro:
        try:
            data_inicio = datetime.datetime.strptime(data_inicio_filtro, '%Y-%m-%d')
            query = query.filter(Movimentacao.data_movimentacao >= data_inicio)
        except ValueError:
            pass # Ignora erro de formato na exportação, ou trate de forma mais robusta
    if data_fim_filtro:
        try:
            data_fim = datetime.datetime.strptime(data_fim_filtro, '%Y-%m-%d') + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
            query = query.filter(Movimentacao.data_movimentacao <= data_fim)
        except ValueError:
            pass

    movimentacoes = query.order_by(Movimentacao.data_movimentacao.desc()).all()

    si = StringIO()
    cw = csv.writer(si)

    # Cabeçalho CSV
    cw.writerow([
        'ID', 'Tipo Movimentacao', 'Numero DANFE', 'Chave Acesso', 
        'Fornecedor (Nome)', 'Fornecedor (CNPJ)', 
        'Operador (Matricula)', 'Operador (Nome)', 'Turno', 
        'Data Movimentacao', 'ID Processa', 'Responsavel (Nome)', 'Status'
    ])

    # Dados
    for mov in movimentacoes:
        fornecedor_nome = mov.fornecedor.nome if mov.fornecedor else ''
        fornecedor_cnpj = mov.fornecedor.cnpj if mov.fornecedor else ''
        operador_nome = mov.operador.nome_completo if mov.operador else ''
        responsavel_nome = mov.responsavel.nome_completo if mov.responsavel else ''

        cw.writerow([
            mov.id, mov.tipo_movimentacao, mov.numero_danfe, mov.chave_acesso,
            fornecedor_nome, fornecedor_cnpj,
            mov.matricula_operador, operador_nome, mov.turno,
            mov.data_movimentacao.strftime('%Y-%m-%d %H:%M:%S'),
            mov.id_processa or '', # Garante string vazia se None
            responsavel_nome,
            mov.status
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=relatorio_movimentacoes.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# Rota para Dashboards visuais (ainda não implementaremos os gráficos aqui, apenas o template)
@relatorios.route('/dashboard_visual')
@login_required
def dashboard_visual():
    return render_template('relatorios/dashboard_visual.html')