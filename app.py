from flask import Flask, render_template, request, redirect,session,jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ====================================
# CONFIGURAÇÕES
# ====================================
app.secret_key = os.getenv("SECRET_KEY", "segredo")

# ====================================
# BANCO RENDER / POSTGRESQL
# ====================================
database_url = os.getenv("DATABASE_URL")

# Corrige URL do Render
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# LOCAL SQLITE
if not database_url:
    database_url = "sqlite:///amor.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ====================================
# MODELOS (BANCO DE DADOS)
# ====================================

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(300), nullable=False)
    idade = db.Column(db.Integer)
    cidade = db.Column(db.String(100))
    bio = db.Column(db.Text)
    foto = db.Column(db.String(300), default="default.png")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Curtida(db.Model):
    __tablename__ = "curtidas"
    id = db.Column(db.Integer, primary_key=True)
    de_usuario = db.Column(db.Integer)
    para_usuario = db.Column(db.Integer)

class Match(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    user1 = db.Column(db.Integer)
    user2 = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

# CLASSE MENSAGEM UNIFICADA (Com áudio, lida e visualização única)
class Mensagem(db.Model):
    __tablename__ = "mensagens"
    id = db.Column(db.Integer, primary_key=True)
    de_usuario = db.Column(db.Integer)
    para_usuario = db.Column(db.Integer)
    mensagem = db.Column(db.Text)
    foto = db.Column(db.String(300))
    audio = db.Column(db.String(300)) # Campo para armazenar o arquivo de áudio
    lida = db.Column(db.Boolean, default=False) # Controle de notificações
    visualizacao_unica = db.Column(db.Boolean, default=False) # Controle do modo WhatsApp sumir
    data = db.Column(db.DateTime, default=datetime.utcnow)

class FotoPerfil(db.Model):
    __tablename__ = "fotos_perfil"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    foto = db.Column(db.String(300))
    avatar = db.Column(db.Boolean, default=False)

# ====================================
# ROTAS E LÓGICA DO SISTEMA
# ====================================

# Apagar Mensagem (Física e Logicamente)
@app.route("/apagar_mensagem/<int:id>")
def apagar_mensagem(id):
    if "user_id" not in session:
        return redirect("/login")

    msg = Mensagem.query.get(id)
    if msg:
        # Só quem enviou pode apagar, ou o sistema deleta se for visualização única concluída
        if msg.de_usuario == session["user_id"] or msg.visualizacao_unica:
            # Apaga o arquivo físico de foto se existir
            if msg.foto:
                caminho_foto = os.path.join(app.config["UPLOAD_FOLDER"], msg.foto)
                if os.path.exists(caminho_foto):
                    os.remove(caminho_foto)
            
            # Apaga o arquivo físico de áudio se existir
            if msg.audio:
                caminho_audio = os.path.join(app.config["UPLOAD_FOLDER"], msg.audio)
                if os.path.exists(caminho_audio):
                    os.remove(caminho_audio)

            db.session.delete(msg)
            db.session.commit()

    return redirect(request.referrer or "/")

@app.route("/upload_foto", methods=["POST"])
def upload_foto():
    if "user_id" not in session:
        return redirect("/login")

    foto = request.files.get("foto")
    if foto:
        extensao = foto.filename.split(".")[-1]
        nome_foto = f"{uuid.uuid4()}.{extensao}"
        caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_foto)
        foto.save(caminho)

        user = Usuario.query.get(session["user_id"])
        user.foto = nome_foto
        db.session.commit()

    return redirect("/")   

@app.route("/avatar/<int:id>")
def avatar(id):
    if "user_id" not in session:
        return redirect("/login")

    fotos = FotoPerfil.query.filter_by(user_id=session["user_id"]).all()
    for f in fotos:
        f.avatar = False

    foto = FotoPerfil.query.get(id)
    if foto:
        foto.avatar = True

    db.session.commit()
    return redirect("/")

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    meu_id = session["user_id"]
    usuarios = Usuario.query.filter(Usuario.id != meu_id).all()
    usuario_logado = Usuario.query.get(meu_id)

    # Criamos o dicionário para contar as mensagens não lidas de cada usuário na Home
    notificacoes = {}
    for u in usuarios:
        total_nao_lidas = Mensagem.query.filter_by(
            de_usuario=u.id, 
            para_usuario=meu_id, 
            lida=False
        ).count()
        notificacoes[u.id] = total_nao_lidas

    return render_template(
        "home.html",
        usuarios=usuarios,
        usuario_logado=usuario_logado,
        notificacoes=notificacoes # Enviando as contagens para o HTML
    )

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]
        idade = request.form["idade"]
        cidade = request.form["cidade"]
        bio = request.form["bio"]

        foto = request.files.get("foto")
        nome_foto = "default.png"

        if foto:
            filename = secure_filename(foto.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            foto.save(caminho)
            nome_foto = filename

        senha_hash = generate_password_hash(senha)
        novo = Usuario(
            nome=nome, email=email, senha=senha_hash,
            idade=idade, cidade=cidade, bio=bio, foto=nome_foto
        )
        db.session.add(novo)
        db.session.commit()
        return redirect("/login")

    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        user = Usuario.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha, senha):
            session["user_id"] = user.id
            return redirect("/")
        return "Login inválido"

    return render_template("login.html")

@app.route("/curtir/<int:id>")
def curtir(id):
    if "user_id" not in session:
        return redirect("/login")

    minha_id = session["user_id"]
    if minha_id == id:
        return redirect("/")

    ja_curtiu = Curtida.query.filter_by(de_usuario=minha_id, para_usuario=id).first()
    if ja_curtiu:
        return redirect("/")

    nova = Curtida(de_usuario=minha_id, para_usuario=id)
    db.session.add(nova)
    db.session.commit()

    curtiu_de_volta = Curtida.query.filter_by(de_usuario=id, para_usuario=minha_id).first()
    if curtiu_de_volta:
        existe_match = Match.query.filter(
            ((Match.user1 == minha_id) & (Match.user2 == id)) |
            ((Match.user1 == id) & (Match.user2 == minha_id))
        ).first()

        if not existe_match:
            novo_match = Match(user1=minha_id, user2=id)
            db.session.add(novo_match)
            db.session.commit()

    return redirect("/")

# Rota de Matches Modificada com contador de mensagens não lidas
@app.route("/matches")
def matches():
    if "user_id" not in session:
        return redirect("/login")

    meu_id = session["user_id"]
    matches_db = Match.query.filter((Match.user1 == meu_id) | (Match.user2 == meu_id)).all()

    lista_matches = []
    notificacoes = {} # Dicionário contendo o total de não lidas {parceiro_id: total}

    for match in matches_db:
        outro_id = match.user2 if match.user1 == meu_id else match.user1
        usuario = Usuario.query.get(outro_id)
        if usuario:
            lista_matches.append(usuario)
            
            # Conta mensagens não lidas vindo deste usuário para mim
            total_nao_lidas = Mensagem.query.filter_by(
                de_usuario=outro_id, 
                para_usuario=meu_id, 
                lida=False
            ).count()
            notificacoes[outro_id] = total_nao_lidas

    return render_template("matches.html", matches=lista_matches, notificacoes=notificacoes)

# Rota do Chat Consolidada (Garante marcação de lidas e aceita áudio e visualização única)
@app.route("/chat/<int:id>", methods=["GET", "POST"])
def chat(id):
    if "user_id" not in session:
        return redirect("/login")

    meu_id = session["user_id"]

    # 1. MARCAR MENSAGENS RECEBIDAS COMO LIDAS AO ENTRAR
    mensagens_nao_lidas = Mensagem.query.filter_by(
        de_usuario=id, 
        para_usuario=meu_id, 
        lida=False
    ).all()
    for m in mensagens_nao_lidas:
        m.lida = True
    db.session.commit()

    # 2. SE FOR ENVIO DE NOVA MENSAGEM (POST)
    if request.method == "POST":
        texto = request.form.get("mensagem")
        foto = request.files.get("foto")
        audio = request.files.get("audio")
        
        once_input = request.form.get("visualizacao_unica")
        modo_once = True if once_input == "1" else False

        nome_foto = None
        nome_audio = None

        if foto and foto.filename != "":
            filename_foto = secure_filename(f"{uuid.uuid4()}_{foto.filename}")
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], filename_foto))
            nome_foto = filename_foto

        if audio and audio.filename != "":
            filename_audio = secure_filename(f"{uuid.uuid4()}_audio.mp3")
            audio.save(os.path.join(app.config["UPLOAD_FOLDER"], filename_audio))
            nome_audio = filename_audio

        if texto or nome_foto or nome_audio:
            try:
                nova = Mensagem(
                    de_usuario=meu_id,
                    para_usuario=id,
                    mensagem=texto,
                    foto=nome_foto,
                    audio=nome_audio,
                    visualizacao_unica=modo_once,
                    lida=False
                )
                db.session.add(nova)
                db.session.commit()

                # ✅ Agora montamos a URL manualmente para evitar erro
                caminho_base = "/static/uploads/"
                usuario_logado = Usuario.query.get(meu_id)

                return jsonify({
                    "sucesso": True,
                    "id": nova.id,
                    "mensagem": nova.mensagem,
                    "foto": bool(nova.foto),
                    "foto_url": caminho_base + nova.foto if nova.foto else "",
                    "audio": bool(nova.audio),
                    "audio_url": caminho_base + nova.audio if nova.audio else "",
                    "visualizacao_unica": nova.visualizacao_unica,
                    "avatar_url": caminho_base + usuario_logado.foto
                })

            except Exception as e:
                db.session.rollback()
                return jsonify({"sucesso": False, "erro": str(e)})

        return jsonify({"sucesso": False, "erro": "Digite uma mensagem ou envie um arquivo"})

    # 3. BUSCA HISTÓRICO DE MENSAGENS
    mensagens = Mensagem.query.filter(
        ((Mensagem.de_usuario == meu_id) & (Mensagem.para_usuario == id)) |
        ((Mensagem.de_usuario == id) & (Mensagem.para_usuario == meu_id))
    ).order_by(Mensagem.data.asc()).all()

    usuario_logado = Usuario.query.get(meu_id)
    usuario_chat = Usuario.query.get(id)

    return render_template(
        "chat.html",
        mensagens=mensagens,
        usuario=usuario_chat,
        usuario_logado=usuario_logado,
        usuario_chat=usuario_chat
    )





@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
 # procurar novas mensagens   
@app.route('/novas_mensagens/<int:id_chat>')
def novas_mensagens(id_chat):
    if "user_id" not in session:
        return jsonify({"novas": []})

    meu_id = session["user_id"]
    # Pega a última mensagem que já está na tela
    ultima_id = request.args.get('ultima_id', 0, type=int)

    # Busca apenas mensagens NOVAS que a outra pessoa enviou
    mensagens_novas = Mensagem.query.filter(
        Mensagem.de_usuario == id_chat,
        Mensagem.para_usuario == meu_id,
        Mensagem.id > ultima_id
    ).order_by(Mensagem.data.asc()).all()

    lista = []
    for msg in mensagens_novas:
        lista.append({
            "id": msg.id,
            "mensagem": msg.mensagem,
            "foto": bool(msg.foto),
            "foto_url": url_for('static', filename=f'uploads/{msg.foto}') if msg.foto else "",
            "audio": bool(msg.audio),
            "audio_url": url_for('static', filename=f'uploads/{msg.audio}') if msg.audio else "",
            "visualizacao_unica": msg.visualizacao_unica,
            "avatar_url": url_for('static', filename=f'uploads/{Usuario.query.get(msg.de_usuario).foto}')
        })

    return jsonify({"novas": lista})
    
# ====================================
# CRIAR BANCO
# ====================================

with app.app_context():
    db.create_all()

# ====================================
# ATUALIZAÇÃO DO POSTGRES (COLE AQUI)
# ====================================
with app.app_context():
    try:
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN lida BOOLEAN DEFAULT FALSE;"))
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN visualizacao_unica BOOLEAN DEFAULT FALSE;"))
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN audio VARCHAR(300);"))
        db.session.commit()
        print("Campos adicionados com sucesso no Postgres do Render!")
    except Exception as e:
        print("Os campos provavelmente já existem ou ocorreu um erro:", e)

# CÓDIGO TEMPORÁRIO - REMOVA DEPOIS DE SUBIR UMA VEZ
with app.app_context():
    try:
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN lida BOOLEAN DEFAULT FALSE;"))
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN visualizacao_unica BOOLEAN DEFAULT FALSE;"))
        db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN audio VARCHAR(300);"))
        db.session.commit()
        print("Campos adicionados com sucesso no Postgres do Render!")
    except Exception as e:
        print("Os campos provavelmente já existem ou ocorreu um erro:", e)
# ====================================
# INICIALIZAÇÃO
# ====================================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
