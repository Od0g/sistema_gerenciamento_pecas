import os

estrutura = [
    ".env",
    "app.py",
    "config.py",
    "requirements.txt",
    "instance/database.db",
    "static/css/style.css",
    "static/js/scripts.js",
    "static/img/",
    "templates/base.html",
    "templates/login.html",
    "templates/dashboard.html",
    "templates/recebimento/recebimento.html",
    "templates/recebimento/confirmacao_recebimento.html",
    "templates/expedicao/expedicao.html",
    "templates/expedicao/confirmacao_expedicao.html",
    "templates/relatorios/relatorios.html",
    "templates/relatorios/dashboard_visual.html",
    "templates/cadastro/cadastro_usuarios.html",
    "templates/cadastro/cadastro_fornecedores.html",
    "templates/cadastro/configuracao_emails.html",
    "templates/errors/404.html",
    "templates/errors/500.html",
    "modules/auth/__init__.py",
    "modules/auth/routes.py",
    "modules/auth/models.py",
    "modules/core/__init__.py",
    "modules/core/routes.py",
    "modules/core/models.py",
    "modules/recebimento/__init__.py",
    "modules/recebimento/routes.py",
    "modules/recebimento/models.py",
    "modules/expedicao/__init__.py",
    "modules/expedicao/routes.py",
    "modules/expedicao/models.py",
    "modules/relatorios/__init__.py",
    "modules/relatorios/routes.py",
    "modules/relatorios/models.py",
    "modules/cadastro/__init__.py",
    "modules/cadastro/routes.py",
    "modules/cadastro/models.py",
    "modules/utils/__init__.py",
    "modules/utils/mail.py",
    "modules/utils/barcode_reader.py"
]

for caminho in estrutura:
    if caminho.endswith('/'):
        os.makedirs(caminho, exist_ok=True)
    else:
        pasta = os.path.dirname(caminho)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(caminho, 'w') as f:
            f.write("")  # cria o arquivo vazio

print("✅ Estrutura de projeto criada com sucesso!")
