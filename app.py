from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
import uuid
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração do Flask
app = Flask(__name__)
app.secret_key = "wosWS@33sSdsss"

DB_PATH = "database.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                sobrenome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agendamentos (
                id TEXT PRIMARY KEY,
                usuario TEXT NOT NULL,
                data TEXT NOT NULL,
                hora_inicio TEXT NOT NULL,
                hora_fim TEXT NOT NULL,
                sala TEXT NOT NULL,
                FOREIGN KEY (usuario) REFERENCES usuarios (usuario)
            )
        ''')
        conn.commit()

# Funções auxiliares
def verificar_usuario(usuario, senha):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT senha FROM usuarios WHERE usuario = ?", (usuario,))
        row = cursor.fetchone()
        if row and check_password_hash(row[0], senha):
            return True
    return False

def cadastrar_usuario(usuario, nome, sobrenome, email, senha):
    senha_hash = generate_password_hash(senha)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usuarios (usuario, nome, sobrenome, email, senha)
            VALUES (?, ?, ?, ?, ?)
        ''', (usuario, nome, sobrenome, email, senha_hash))
        conn.commit()

def carregar_agendamentos():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT agendamentos.id, usuarios.nome, usuarios.sobrenome, agendamentos.data,
                   agendamentos.hora_inicio, agendamentos.hora_fim, agendamentos.sala
            FROM agendamentos
            JOIN usuarios ON agendamentos.usuario = usuarios.usuario
        ''')
        return cursor.fetchall()

def salvar_agendamento(usuario, data, hora_inicio, hora_fim, sala):
    agendamento_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agendamentos (id, usuario, data, hora_inicio, hora_fim, sala)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (agendamento_id, usuario, data, hora_inicio, hora_fim, sala))
        conn.commit()

def gerar_horarios():
    horarios = []
    inicio = datetime.strptime("07:30", "%H:%M")
    fim = datetime.strptime("17:30", "%H:%M")
    while inicio <= fim:
        if inicio.strftime("%H:%M") != "12:30":
            horarios.append(inicio.strftime("%H:%M"))
        inicio += timedelta(minutes=30)
    return horarios

def obter_nome_sobrenome(usuario):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome, sobrenome FROM usuarios WHERE usuario = ?", (usuario,))
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
    return "Usuário", "Desconhecido"

def gerar_token_reset():
    return secrets.token_urlsafe(32)

def salvar_token_reset(usuario, token):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reset_tokens (
                usuario TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Remove existing tokens for this user
        cursor.execute("DELETE FROM reset_tokens WHERE usuario = ?", (usuario,))
        # Insert new token
        cursor.execute('''
            INSERT INTO reset_tokens (usuario, token)
            VALUES (?, ?)
        ''', (usuario, token))
        conn.commit()

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import traceback

def enviar_email_reset(email, token):
    remetente = "suporte@alphaeletrica.ind.br"  # Seu e-mail de suporte
    senha_remetente = "YpaH7eswZb@MAGq4"  # Senha do servidor de entrada (IMAP)

    mensagem = MIMEMultipart()
    mensagem['From'] = remetente
    mensagem['To'] = email
    mensagem['Subject'] = "Redefinição de Senha - Alpha Elétrica"

    corpo = f"""
    Você solicitou a redefinição de senha para sua conta.

    Clique no link abaixo para redefinir sua senha:
    http://192.168.55.209:5001/redefinir-senha/{token}

    Este link é válido por 1 hora.

    Se você não solicitou esta redefinição, ignore este email.

    Atenciosamente,
    Equipe Alpha Elétrica
    """

    mensagem.attach(MIMEText(corpo, 'plain'))

    try:
        print("Conectando ao servidor SMTP com SSL...")
        # Conexão usando SSL/TLS na porta 465
        with smtplib.SMTP_SSL('smtp.alphaeletrica.ind.br', 465) as servidor:
            servidor.ehlo()  
            servidor.login(remetente, senha_remetente)  
            servidor.send_message(mensagem)  # Envia a mensagem
        return True
    except Exception as e:
        print("Erro ao enviar e-mail:")
        traceback.print_exc()  # Exibe detalhes do erro
        return False



def validar_token_reset(usuario, token):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM reset_tokens 
            WHERE usuario = ? AND token = ? 
            AND datetime('now', '-1 hour') <= data_criacao
        ''', (usuario, token))
        return cursor.fetchone() is not None

# Rotas
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        if verificar_usuario(usuario, senha):
            session["usuario"] = usuario
            return redirect(url_for("agenda"))
        flash("Usuário ou senha inválidos!", "danger")
    return render_template("login.html")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        usuario = request.form["usuario"]
        nome = request.form["nome"]
        sobrenome = request.form["sobrenome"]
        email = request.form["email"]
        senha = request.form["senha"]

        # Verificar se o usuário contém espaços
        if " " in usuario:
            flash("O nome de usuário não pode conter espaços.", "danger")
            return render_template("cadastro.html")

        if all([usuario, nome, sobrenome, email, senha]):
            if email.endswith("@alphaeletrica.ind.br"):
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()

                    cursor.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,))
                    if cursor.fetchone():
                        flash("Usuário já cadastrado!", "danger")
                        return render_template("cadastro.html")

                    cursor.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,))
                    if cursor.fetchone():
                        flash("Email já cadastrado!", "danger")
                        return render_template("cadastro.html")
                    
                    cursor.execute(
                        "SELECT 1 FROM usuarios WHERE nome = ? AND sobrenome = ?", 
                        (nome, sobrenome)
                    )
                    if cursor.fetchone():
                        flash("Esta pessoa já está cadastrada!", "danger")
                        return render_template("cadastro.html")

                try:
                    cadastrar_usuario(usuario, nome, sobrenome, email, senha)
                    flash("Usuário cadastrado com sucesso!", "success")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Erro ao cadastrar usuário. Por favor, tente novamente.", "danger")
            else:
                flash("O e-mail deve ser do domínio @alphaeletrica.ind.br", "danger")
        else:
            flash("Preencha todos os campos!", "danger")

    return render_template("cadastro.html")

@app.route("/agenda", methods=["GET", "POST"])
def agenda():
    if "usuario" not in session:
        return jsonify({"success": False, "message": "Faça login para acessar sua agenda."})

    usuario = session["usuario"]
    nome, sobrenome = obter_nome_sobrenome(usuario)

    if request.method == "POST":
        data = request.form.get("data")
        hora_inicio = request.form.get("hora_inicio")
        hora_fim = request.form.get("hora_fim")
        sala = request.form.get("sala")

        if not all([data, hora_inicio, hora_fim, sala]):
            return jsonify({
                "success": False, 
                "message": "Todos os campos são obrigatórios!"
            })

        agendamentos = carregar_agendamentos()
        
        if any(
            a[3] == data and a[6] == sala and hora_inicio < a[5] and hora_fim > a[4]
            for a in agendamentos
        ):
            return jsonify({
                "success": False, 
                "message": "Conflito de horários!"
            })

        try:
            salvar_agendamento(usuario, data, hora_inicio, hora_fim, sala)
            return jsonify({"success": True})
        except Exception as e:
            print(f"Erro ao salvar agendamento: {e}")
            return jsonify({
                "success": False, 
                "message": "Erro interno ao salvar agendamento."
            })

    agendamentos = carregar_agendamentos()
    eventos = [
        {
            "id": a[0],
            "title": f"{a[1]} {a[2]}",
            "start": f"{a[3]}T{a[4]}",
            "end": f"{a[3]}T{a[5]}",
            "sala": a[6],
            "nome": a[1],
            "sobrenome": a[2],
        }
        for a in agendamentos
    ]
    horarios_disponiveis = gerar_horarios()
    return render_template(
        "agenda.html",
        eventos=eventos,
        salas=["Sala 1", "Sala 2", "Sala Fábrica"],
        horarios_disponiveis=horarios_disponiveis,
        nome=nome,
        sobrenome=sobrenome,
        usuario=usuario
    )

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Você saiu da sessão.", "success")
    return redirect(url_for("login"))

@app.route("/cancelar", methods=["POST"])
def cancelar():
    try:
        # Verificar se o usuário está logado
        usuario_logado = session.get("usuario")
        if not usuario_logado:
            return jsonify({
                "status": "erro", 
                "message": "Usuário não autenticado."
            }), 401

        # Obter o ID do agendamento do formulário
        agendamento_id = request.form.get("agendamento_id")
        if not agendamento_id:
            return jsonify({
                "status": "erro", 
                "message": "ID do agendamento não fornecido."
            }), 400

        # Estabelecer conexão com o banco de dados
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Buscar detalhes do agendamento
            cursor.execute(
                "SELECT usuario FROM agendamentos WHERE id = ?", 
                (agendamento_id,)
            )
            agendamento = cursor.fetchone()

            # Verificar se o agendamento existe
            if not agendamento:
                return jsonify({
                    "status": "erro", 
                    "message": "Agendamento não encontrado."
                }), 404

            # Verificar se o usuário logado é o dono do agendamento
            if agendamento[0] != usuario_logado:
                return jsonify({
                    "status": "erro", 
                    "message": "Você não tem permissão para cancelar este agendamento."
                }), 403

            # Realizar a exclusão do agendamento
            cursor.execute(
                "DELETE FROM agendamentos WHERE id = ? AND usuario = ?", 
                (agendamento_id, usuario_logado)
            )
            
            # Verificar se a exclusão foi realizada com sucesso
            if cursor.rowcount == 0:
                conn.rollback()
                return jsonify({
                    "status": "erro", 
                    "message": "Falha ao cancelar o agendamento."
                }), 500
            
            # Confirmar a transação
            conn.commit()

        # Retornar sucesso
        return jsonify({
            "status": "sucesso", 
            "message": "Agendamento cancelado com sucesso."
        }), 200

    except sqlite3.Error as e:
        # Tratamento de erro de banco de dados
        return jsonify({
            "status": "erro", 
            "message": f"Erro no banco de dados: {str(e)}"
        }), 500
    except Exception as e:
        # Tratamento de erro genérico
        return jsonify({
            "status": "erro", 
            "message": f"Erro inesperado: {str(e)}"
        }), 500
    
@app.route("/esqueci-senha", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        
        # Verificar se o email existe
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT usuario FROM usuarios WHERE email = ?", (email,))
            usuario = cursor.fetchone()
        
        if usuario:
            # Gerar token de reset
            token = gerar_token_reset()
            salvar_token_reset(usuario[0], token)
            
            # Tentar enviar email
            if enviar_email_reset(email, token):
                flash("Email de redefinição de senha enviado!", "success")
            else:
                flash("Erro ao enviar email de redefinição.", "danger")
        else:
            flash("Email não encontrado.", "danger")
    
    return render_template("forgot_password.html")

@app.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def reset_password(token):
    # Encontrar o usuário associado ao token
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT usuario FROM reset_tokens 
            WHERE token = ? 
            AND datetime('now', '-1 hour') <= data_criacao
        ''', (token,))
        result = cursor.fetchone()
    
    if not result:
        flash("Token inválido ou expirado.", "danger")
        return redirect(url_for("login"))
    
    usuario = result[0]
    
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirmar_senha = request.form.get("confirmar_senha")
        
        if nova_senha == confirmar_senha:
            # Atualizar senha
            senha_hash = generate_password_hash(nova_senha)
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE usuarios SET senha = ? WHERE usuario = ?", (senha_hash, usuario))
                
                # Excluir o token
                cursor.execute("DELETE FROM reset_tokens WHERE usuario = ?", (usuario,))
                conn.commit()
            
            flash("Senha redefinida com sucesso!", "success")
            return redirect(url_for("login"))
        else:
            flash("As senhas não coincidem.", "danger")
    
    return render_template("reset_password.html", token=token)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, ssl_context=('cert.pem', 'key.pem'))