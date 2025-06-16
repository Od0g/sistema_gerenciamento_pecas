from app import db # Importe 'db' do app.py

class Fornecedor(db.Model):
    __tablename__ = 'Fornecedores'

    id = db.Column(db.Integer, primary_key=True)
    codigo_fornecedor = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(18), unique=True, nullable=False)
    data_inclusao = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relacionamento com Movimentacoes (opcional, mas bom para clareza)
    movimentacoes = db.relationship('Movimentacao', backref='fornecedor', lazy=True)

    def __repr__(self):
        return f'<Fornecedor {self.nome} ({self.cnpj})>'

# ... (código anterior de Fornecedor) ...

class Movimentacao(db.Model):
    __tablename__ = 'Movimentacoes'

    id = db.Column(db.Integer, primary_key=True)
    tipo_movimentacao = db.Column(db.Enum('Recebimento', 'Expedicao'), nullable=False)
    numero_danfe = db.Column(db.String(100), nullable=False)
    chave_acesso = db.Column(db.String(44), unique=True, nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('Fornecedores.id'), nullable=False)
    matricula_operador = db.Column(db.String(50), db.ForeignKey('Usuarios.matricula'), nullable=False)
    turno = db.Column(db.String(20), nullable=False)
    data_movimentacao = db.Column(db.DateTime, default=db.func.current_timestamp())
    id_processa = db.Column(db.String(100)) # Apenas para expedição
    responsavel_id = db.Column(db.Integer, db.ForeignKey('Usuarios.id')) # ID do usuário (DLI/PQM) que é o responsável, apenas para recebimento
    status = db.Column(db.Enum('Pendente', 'Concluido'), nullable=False, default='Pendente')

    # Relacionamento com Usuarios (operador e responsável)
    operador = db.relationship('User', foreign_keys=[matricula_operador],
                               primaryjoin="Movimentacao.matricula_operador == User.matricula", lazy=True)
    responsavel = db.relationship('User', foreign_keys=[responsavel_id],
                                  primaryjoin="Movimentacao.responsavel_id == User.id", lazy=True)


    def __repr__(self):
        return f'<Movimentacao {self.tipo_movimentacao} - {self.numero_danfe}>'

# ... (código anterior de Movimentacao) ...

class ConfiguracaoEmail(db.Model):
    __tablename__ = 'ConfiguracoesEmails'

    id = db.Column(db.Integer, primary_key=True)
    tipo_email = db.Column(db.String(50), unique=True, nullable=False)
    assunto = db.Column(db.String(255), nullable=False)
    corpo_template = db.Column(db.Text, nullable=False)
    destinatarios_adicionais = db.Column(db.Text, nullable=True) # <<< NOVA COLUNA: Lista de e-mails separados por vírgula

    def __repr__(self):
        return f'<ConfiguracaoEmail {self.tipo_email}>'

