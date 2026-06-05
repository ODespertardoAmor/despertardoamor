from flask import Flask, render_template, request, redirect, session
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
    verificado = db.Column(db.Boolean, default=False)  # começa como não verificado
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
    if not msg:
        return redirect(request.referrer or "/")

    # Permite apagar se for o dono OU se for visualização única
    if msg.de_usuario == session["user_id"] or msg.visualizacao_unica:
        
        # Caminho completo da pasta de uploads
        pasta_upload = app.config.get("UPLOAD_FOLDER", "")

        # Apaga foto
        if msg.foto:
            caminho_foto = os.path.join(pasta_upload, msg.foto)
            print(f"Tentando apagar foto: {caminho_foto}")  # Para ver no terminal
            if os.path.exists(caminho_foto):
                os.remove(caminho_foto)
                print("Foto apagada com sucesso")
            else:
                print("Foto NÃO encontrada no caminho")

        # Apaga ÁUDIO - AQUI ESTAVA O POSSÍVEL PROBLEMA
        if msg.audio:
            caminho_audio = os.path.join(pasta_upload, msg.audio)
            print(f"Tentando apagar áudio: {caminho_audio}")  # Para ver no terminal
            if os.path.exists(caminho_audio):
                os.remove(caminho_audio)
                print("Áudio apagado com sucesso")
            else:
                print("Áudio NÃO encontrado no caminho")

        # Apaga do banco
        db.session.delete(msg)
        db.session.commit()
        print("Mensagem apagada do banco")

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

    # ✅ ADICIONE AQUI: Contagem TOTAL de todas as mensagens não lidas
    total_notificacoes = Mensagem.query.filter_by(
        para_usuario=meu_id,
        lida=False
    ).count()

    return render_template(
        "home.html",
        usuarios=usuarios,
        usuario_logado=usuario_logado,
        notificacoes=notificacoes,
        total_notificacoes=total_notificacoes  # ✅ ADICIONE AQUI TAMBÉM
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

    # ✅ Calcula o TOTAL geral de mensagens não lidas uma vez só, fora do laço
    total_notificacoes = Mensagem.query.filter_by(
        para_usuario=meu_id,
        lida=False
    ).count()

    for match in matches_db:
        outro_id = match.user2 if match.user1 == meu_id else match.user1
        usuario = Usuario.query.get(outro_id)
        if usuario:
            lista_matches.append(usuario)
            
            # Conta mensagens não lidas vindo deste usuário específico
            total_nao_lidas = Mensagem.query.filter_by(
                de_usuario=outro_id, 
                para_usuario=meu_id, 
                lida=False
            ).count()
            notificacoes[outro_id] = total_nao_lidas

    # ✅ Retorna passando todas as variáveis corretamente
    return render_template(
        "matches.html",
        matches=lista_matches,
        notificacoes=notificacoes,
        total_notificacoes=total_notificacoes
    )

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
        audio = request.files.get("audio") # Pega o áudio do gravador
        
        # Verifica se ativou o botão de visualização única
        once_input = request.form.get("visualizacao_unica")
        modo_once = True if once_input == "1" else False

        nome_foto = None
        nome_audio = None

        # Salva Foto se houver
        if foto and foto.filename != "":
            filename_foto = secure_filename(f"{uuid.uuid4()}_{foto.filename}")
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], filename_foto))
            nome_foto = filename_foto

        # Salva Áudio se houver
        if audio and audio.filename != "":
            filename_audio = secure_filename(f"{uuid.uuid4()}_audio.mp3")
            audio.save(os.path.join(app.config["UPLOAD_FOLDER"], filename_audio))
            nome_audio = filename_audio

        if texto or nome_foto or nome_audio:
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

    # 3. BUSCA HISTÓRICO DE MENSAGENS PARA EXIBIR
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
#with app.app_context():
    #try:
       # db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN lida BOOLEAN DEFAULT FALSE;"))
        #db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN visualizacao_unica BOOLEAN DEFAULT FALSE;"))
        #db.session.execute(db.text("ALTER TABLE mensagens ADD COLUMN audio VARCHAR(300);"))
        #db.session.commit()
       # print("Campos adicionados com sucesso no Postgres do Render!")
    #except Exception as e:
        #print("Os campos provavelmente já existem ou ocorreu um erro:", e)
# ====================================
# INICIALIZAÇÃO
# ====================================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
