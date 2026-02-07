from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
# SQLAlchemyのrelationshipはdb.relationshipを使うのがいいらしい。
from sqlalchemy.orm import joinedload
from functools import warps

# 定数定義
EMAIL_PATTERN = EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
SESSION_DAYS = 30

# Flaskアプリのインスタンス作成
app = Flask(__name__)

# セッション設定
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS)
# SQLiteデータベースの設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
# SQLAlchemyのイベント通知無効化
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# SQLAlchemyオブジェクト生成
db = SQLAlchemy(app)

#コンテナを再起動するたびにセッションが無効かされるので別方法を取る。
#app.config['SECRET_KEY'] = os.urandom(24)

# SECRET_KEYを.envに作成する。
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


# Userモデル作成
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    mailaddress = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)

    def __repr__(self):
        #ユーザーIDもあった方が後で検索とかし易いと思う
        #return f'<User {self.username}>'
        return f'<User id={self.id} username={self.username}>'
   
    # パスワードの保存(ハッシュ値)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
   
    # パスワードの検証
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

#Postモデル作成
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utdnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'

#ログイン「有」確認用デコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#ログイン「無」確認用デコレータ
def not_logged_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is not None:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

#DB作成
with app.app_context():
    db.create_all()

#ルートページのリダイレクト処理
@app.route('/', methods=['GET'])
@login_required
def index():
    return redirect(url_for('posts'))

#ログイン画面の表示
@app.route('/login')
def login():
    return render_template('login.html')

#ログイン処理
@app.route('/submit', methods = ['POST'])
def submit():
    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()

    #追加空チェック
    if not username or not password:
        return redirect(url_for('login'))

    if user and user.check_password(password):
        #セッションにuser_idを追加
        session['user_id'] = user.id
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

#GETで処理したいことが増えてもいいようにPOSTとプログラムを分ける。
#サインアップページの表示(GET)
@app.route('/signup', methods=['GET'])
@not_logged_required
def signup_view():
    return render_template(sighup.html)

#ログアウト処理
@app.route('/logout')
def logout():
    #ログアウト処理時に使用。session.clear()よりbest!!
    session.pop('user_id', None)
    return redirect(url_for('login'))

#サインアップ処理(POST)
@app.route('/signup', methods = ['POST'])
def signup():
    username = request.form['username']
    mailaddress = request.form['mailaddress'] 
    password = request.form['password']
    password_confirmation = request.form['password_confirmation']

    # 空チェック
    if not username or not mailaddress or not password or not password_confirmation:
        #flash("空のフォームがあります", 'error')
        return redirect(url_for('signup'))

    # メールアドレス型式チェック
    if not re.match(EMAIL_PATTERN, mailaddress):
        #flash("正しいメールアドレスの型式ではありません", 'error')
        return redirect(url_for('signup'))

    # 既存ユーザー確認
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        #flash("既に登録されているユーザー名です", 'error')
        return redirect(url_for('signup'))

    # 既存メールアドレス確認
    existing_mailadress = User.query.filter_by(mailaddress=mailaddress).first()
        #flash("既に登録されているメールアドレスです", 'error')
        return redirect(url_for('signup'))

    # パスワード一致確認
    if password != password_confirmation:
        #flash("二つのパスワードの値が異なっています", 'error')
        return redirect(url_for('signup'))

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    print(f"新規登録成功: ユーザー '{username}' がデータベースに追加されました。")

    return redirect(url_for('home'))

# 投稿一覧画面表示
@app.route('/home')
@login_required
def home():
    # 投稿一覧と合わせて投稿者情報も一緒に取得する
    posts = Post.query.options(joinedload(Post.author)).order_by(Post.created_at.desc()).all()
    return render_template('home.html', posts=posts)

@app.route('/posts', methods = ['GET', 'POST'])
def posts():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        content = request.form['post_body']
        if content:
            new_post = Post(content=content, user_id=user_id)
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('home'))
    return render_template('posts.html')

# 本人プロフィール画面表示
@app.route('/profile')
@login_required
def profile():
    user = User.query.get(user_id)
    if not user:
            return redirect(url_for('login'))
    return render_template('profile.html' , post=user)

# 他人プロフィール画面表示
@app.route('/others_profile/<int:user_id>')
def others_profile(user_id):
    user = User.query.get(user_id)
    if not user:
            return redirect(url_for('home'))
    return render_template('others_profile.html' , post=user)

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)