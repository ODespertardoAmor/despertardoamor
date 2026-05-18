from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
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
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

# LOCAL SQLITE
if not database_url:
    database_url = "sqlite:///amor.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ====================================
# TABELA DE USUÁRIOS
# ====================================

class Usuario(db.Model):

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    senha = db.Column(db.String(300), nullable=False)

    idade = db.Column(db.Integer)

    cidade = db.Column(db.String(100))

    bio = db.Column(db.Text)

    foto = db.Column(
        db.String(300),
        default="default.png"
    )

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# ====================================
# CURTIDAS
# ====================================

class Curtida(db.Model):

    __tablename__ = "curtidas"

    id = db.Column(db.Integer, primary_key=True)

    de_usuario = db.Column(db.Integer)

    para_usuario = db.Column(db.Integer)

# ====================================
# MATCHES
# ====================================

class Match(db.Model):

    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)

    user1 = db.Column(db.Integer)

    user2 = db.Column(db.Integer)

    criado_em = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# ====================================
# MENSAGENS
# ====================================

class Mensagem(db.Model):

    __tablename__ = "mensagens"

    id = db.Column(db.Integer, primary_key=True)

    de_usuario = db.Column(db.Integer)

    para_usuario = db.Column(db.Integer)

    mensagem = db.Column(db.Text)

    foto = db.Column(db.String(300))

    data = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    
#======≠===Foto perfil=======
class FotoPerfil(db.Model):

    __tablename__ = "fotos_perfil"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer)

    foto = db.Column(db.String(300))

    avatar = db.Column(
        db.Boolean,
        default=False
    )
#========apagar msm======
@app.route("/apagar_mensagem/<int:id>")
def apagar_mensagem(id):

    if "user_id" not in session:
        return redirect("/login")

    msg = Mensagem.query.get(id)

    if msg:

        if msg.de_usuario == session["user_id"]:

            db.session.delete(msg)
            db.session.commit()

    return redirect(request.referrer)
#=============rota perfil======≠===
@app.route("/upload_foto", methods=["POST"])
def upload_foto():

    if "user_id" not in session:
        return redirect("/login")

    foto = request.files.get("foto")

    if foto and foto.filename != "":

        filename = secure_filename(foto.filename)

        caminho = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        foto.save(caminho)

        nova = FotoPerfil(
            user_id=session["user_id"],
            foto=filename
        )

        db.session.add(nova)
        db.session.commit()

    return redirect("/")
#===========Definir avatar==≠===
@app.route("/avatar/<int:id>")
def avatar(id):

    if "user_id" not in session:
        return redirect("/login")

    fotos = FotoPerfil.query.filter_by(
        user_id=session["user_id"]
    ).all()

    for f in fotos:
        f.avatar = False

    foto = FotoPerfil.query.get(id)

    if foto:
        foto.avatar = True

    db.session.commit()

    return redirect("/")
# ====================================
# HOME
# ====================================
@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    usuarios = Usuario.query.filter(
        Usuario.id != session["user_id"]
    ).all()

    usuario_logado = Usuario.query.get(
        session["user_id"]
    )

    return render_template(
        "home.html",
        usuarios=usuarios,
        usuario_logado=usuario_logado
    )


# ====================================
# CADASTRO
# ====================================
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        idade = request.form["idade"]
        cidade = request.form["cidade"]
        bio = request.form["bio"]

        foto = request.files["foto"]

        nome_foto = "default.png"

        if foto:

            filename = secure_filename(foto.filename)

            caminho = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            foto.save(caminho)

            nome_foto = filename

        senha_hash = generate_password_hash(senha)

        novo = Usuario(
            nome=nome,
            email=email,
            senha=senha_hash,
            idade=idade,
            cidade=cidade,
            bio=bio,
            foto=nome_foto
        )

        db.session.add(novo)
        db.session.commit()

        return redirect("/login")

    return render_template("cadastro.html")

# ====================================
# LOGIN
# ====================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        senha = request.form["senha"]

        user = Usuario.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.senha,
            senha
        ):

            session["user_id"] = user.id

            return redirect("/")

        return "Login inválido"

    return render_template("login.html")

# ====================================
# CURTIR
# ====================================

@app.route("/curtir/<int:id>")
def curtir(id):

    if "user_id" not in session:
        return redirect("/login")

    minha_id = session["user_id"]

    if minha_id == id:
        return redirect("/")

    ja_curtiu = Curtida.query.filter_by(
        de_usuario=minha_id,
        para_usuario=id
    ).first()

    if ja_curtiu:
        return redirect("/")

    nova = Curtida(
        de_usuario=minha_id,
        para_usuario=id
    )

    db.session.add(nova)
    db.session.commit()

    # VERIFICAR MATCH

    curtiu_de_volta = Curtida.query.filter_by(
        de_usuario=id,
        para_usuario=minha_id
    ).first()

    if curtiu_de_volta:

        existe_match = Match.query.filter(
            (
                (Match.user1 == minha_id) &
                (Match.user2 == id)
            )
            |
            (
                (Match.user1 == id) &
                (Match.user2 == minha_id)
            )
        ).first()

        if not existe_match:

            novo_match = Match(
                user1=minha_id,
                user2=id
            )

            db.session.add(novo_match)
            db.session.commit()

    return redirect("/")

# ====================================
# MATCHES
# ====================================
@app.route("/matches")
def matches():

    if "user_id" not in session:
        return redirect("/login")

    meu_id = session["user_id"]

    matches_db = Match.query.filter(
        (Match.user1 == meu_id) |
        (Match.user2 == meu_id)
    ).all()

    lista_matches = []

    for match in matches_db:

        if match.user1 == meu_id:
            outro_id = match.user2
        else:
            outro_id = match.user1

        usuario = Usuario.query.get(outro_id)

        lista_matches.append(usuario)

    return render_template(
        "matches.html",
        matches=lista_matches
    )

    

# ====================================
# CHAT
# ====================================


@app.route("/chat/<int:id>", methods=["GET", "POST"])
def chat(id):

    if "user_id" not in session:
        return redirect("/login")

    meu_id = session["user_id"]

    if request.method == "POST":

        texto = request.form.get("mensagem")

        foto = request.files.get("foto")

        nome_foto = None

        if foto and foto.filename != "":

            filename = secure_filename(foto.filename)

            caminho = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            foto.save(caminho)

            nome_foto = filename

        nova = Mensagem(
            de_usuario=meu_id,
            para_usuario=id,
            mensagem=texto,
            foto=nome_foto
        )

        db.session.add(nova)
        db.session.commit()

    mensagens = Mensagem.query.filter(
        (
            (Mensagem.de_usuario == meu_id)
            &
            (Mensagem.para_usuario == id)
        )
        |
        (
            (Mensagem.de_usuario == id)
            &
            (Mensagem.para_usuario == meu_id)
        )
    ).order_by(Mensagem.data.asc()).all()

    usuario = Usuario.query.get(id)

    return render_template(
        "chat.html",
        mensagens=mensagens,
        usuario=usuario
    )



# ====================================
# LOGOUT
# ====================================

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
# RENDER
# ====================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
