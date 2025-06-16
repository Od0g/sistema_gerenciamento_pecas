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

# Rota para Dashboards visuais 
@relatorios.route('/dashboard_visual', methods=['GET']) # Adicione methods=['GET']
@login_required
def dashboard_visual():
    # Permissões: Somente Gestores e LSL podem ver dashboards visuais
    if not current_user.tipo_usuario in ['Gestor', 'LSL']:
        flash('Você não tem permissão para acessar esta página de dashboard.', 'danger')
        return redirect(url_for('home'))

    # Dados para "Notas por Fornecedor"
    # Contagem de movimentações (recebimento ou expedição) por fornecedor
    movimentacoes_por_fornecedor = db.session.query(
        Fornecedor.nome,
        db.func.count(Movimentacao.id)
    ).join(Movimentacao).group_by(Fornecedor.nome).all()

    labels_fornecedores = [item[0] for item in movimentacoes_por_fornecedor]
    data_fornecedores = [item[1] for item in movimentacoes_por_fornecedor]

    # Dados para "Movimentações por Dia/Turno"
    # Contagem de movimentações por dia (últimos 7 dias, por exemplo)
    sete_dias_atras = datetime.now() - timedelta(days=7)
    movimentacoes_por_dia = db.session.query(
        db.func.date(Movimentacao.data_movimentacao),
        db.func.count(Movimentacao.id)
    ).filter(Movimentacao.data_movimentacao >= sete_dias_atras).group_by(db.func.date(Movimentacao.data_movimentacao)).order_by(db.func.date(Movimentacao.data_movimentacao)).all()

    labels_dias = [item[0].strftime('%d/%m') for item in movimentacoes_por_dia]
    data_dias = [item[1] for item in movimentacoes_por_dia]

    # Dados para "Tempo Médio entre Recebimento e Expedição"
    # Apenas para movimentações 'Concluido' (recebidas e expedidas)
    tempos_entre_mov = db.session.query(Movimentacao).filter(
        Movimentacao.status == 'Concluido',
        Movimentacao.tipo_movimentacao == 'Expedicao' # Garante que estamos pegando a data da expedição
    ).all()

    total_diff_seconds = 0
    count_concluidas = 0

    for mov_expedicao in tempos_entre_mov:
        # Encontra a movimentação de recebimento correspondente pela chave de acesso
        mov_recebimento = Movimentacao.query.filter(
            Movimentacao.chave_acesso == mov_expedicao.chave_acesso,
            Movimentacao.tipo_movimentacao == 'Recebimento'
        ).first()

        if mov_recebimento and mov_recebimento.data_movimentacao and mov_expedicao.data_movimentacao:
            time_diff = mov_expedicao.data_movimentacao - mov_recebimento.data_movimentacao
            total_diff_seconds += time_diff.total_seconds()
            count_concluidas += 1

    tempo_medio_horas = 0
    if count_concluidas > 0:
        tempo_medio_horas = (total_diff_seconds / count_concluidas) / 3600 # Converter para horas

    tempo_medio_str = f"{tempo_medio_horas:.2f} horas" if tempo_medio_horas > 0 else "N/A"
    
    return render_template('relatorios/dashboard_visual.html',
                           labels_fornecedores=labels_fornecedores,
                           data_fornecedores=data_fornecedores,
                           labels_dias=labels_dias,
                           data_dias=data_dias,
                           tempo_medio_str=tempo_medio_str)