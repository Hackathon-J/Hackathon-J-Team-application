from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
#SQLAlchemyのrelationshipはdb.relationshipを使うのがいいらしい。
from sqlalchemy.orm import joinedload
from functools import wraps
import re 

#定数定義
EMAIL_PATTERN = EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
SESSION_DAYS = 30

#Flaskアプリのインスタンス作成
app = Flask(__name__)

#セッション設定
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS)
#SQLデータベースの指定
#SQLiteを指定⇒MYSQLの指定が必要だと思うので変更
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@db:3306/"
    f"{os.getenv('DB_DATABASE')}"
)
#SQLAlchemyのイベント通知無効化
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


#コンテナを再起動するたびにセッションが無効かされるので別方法を取る。
#app.config['SECRET_KEY'] = os.urandom(24)
#SECRET_KEYを.envに作成する。 line30-35おーちゃん追加
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if app.config['SECRET_KEY'] is None:
    raise RuntimeError("SECRET_KEYが設定されていません。'.env'ファイルを確認してください。")
db = SQLAlchemy(app)

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

#データベース共通部分を親クラスとしてまとめた
class BaseModel(db.Model):
    __abstract__ = True #テーブルを作らない

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                           onupdate=datetime.utcnow, nullable=False )
    
    #created_atの日本時間変換
    @property
    def created_at_jst(self):
        return self.jst_Change(self.created_at)
    
    #updated_atの日本時間変換
    @property
    def updated_at_jst(self):
        return self.jst_Change(self.updated_at)
    
    #計算式_UTC+9hour
    @staticmethod
    def jst_Change(dt):
        if dt is None:
            return None
        return dt + timedelta(hours=9)

#Userモデル作成
class User(BaseModel):
    __tablename__ = "users"
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    mailaddress = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    #UserとProfileを1対1に結び付ける設定
    profile = db.relationship('Profile', backref='user', uselist=False)

    def __repr__(self):
        #ユーザーIDもあった方が後で検索とかし易いと思う
        #return f'<User {self.username}>'
        return f'<User id={self.id} username={self.username}>'

    #パスワードの保存(ハッシュ値)
    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256')

    #パスワードの検証
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

#Postモデル作成
class Post(BaseModel):
    __tablename__ = "posts"
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    learning_time = db.Column(db.Integer) #追加byおーちゃん2/10

    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'
    @property #line77〜91追加byおーちゃん2/10
    def formatted_learning_time(self):
        if self.learning_time is None:
            return "未記録"
        
        hours = self.learning_time // 60
        minutes = self.learning_time % 60
        if hours > 0 and minutes > 0:
            return f"{hours}時間{minutes}分"
        elif hours > 0:
            return f"{hours}時間"
        elif minutes > 0:
            return f"{minutes}分"
        else:
            return "0分"

#Profileモデル作成
class Profile(BaseModel):
    __tablename__ = "profiles"
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    content = db.Column(db.Text)
    icon_path = db.Column(db.String(255))
    header_path = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<Profile id={self.id} user_id={self.user_id}>'

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
@app.route('/submit', methods=['POST'])
def submit():
    # request.formはrequestオブジェクト(インスタンス？)のform属性(つまり変数)のこと
    # requestオブジェクトには送られてきた大量のHTTPリクエストデータが入っている
    # request.formは<form>タグから送られてきたデータを扱う。[]に入れるのは<input ~ name="この部分">
    username = request.form['username']
    password = request.form['password']

    # Flask-SQLAlchemyから引用したqueryプロパティ(SELECT文的な)とfilter_byメソッド(WHERE句的な)
    # 上記をUserクラス(Userテーブル)に適用している。usernameカラムが先ほど定義したusername変数と一致している.first()(LIMIT 1の意味)
    user = User.query.filter_by(username=username).first()

    #空チェック
    if not username or not password:
        return redirect(url_for('login'))

    if user and user.check_password(password):
        #セッションにuser_idを追加
        session['user_id'] = user.id
        session.permanent = True  # おーちゃん追加
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

#GETで処理したいことが増えてもいいようにPOSTとプログラムを分ける。
#サインアップページの表示(GET)
@app.route('/signup', methods=['GET'])
@not_logged_required
def signup_view():
    return render_template('signup.html')
    
#サインアップ処理(POST)
@app.route('/signup', methods=['POST'])
def signup_post():
    username = request.form['username']
    mailaddress = request.form['mailaddress']
    password = request.form['password']
    password_confirmation = request.form['password_confirmation']
    if not username or not mailaddress or not password or not password_confirmation:
        return redirect(url_for('signup_view'))
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return redirect(url_for('signup_view'))
    if password != password_confirmation:
        return redirect(url_for('signup_view'))
    new_user = User(username=username, mailaddress=mailaddress)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    session['user_id'] = new_user.id
    session.permanent = True  # line159-160おーちゃん追加
    return redirect(url_for('home'))

#ログアウト処理
@app.route('/logout')
def logout():
    #ログアウト処理時に使用。session.clear()よりbest!!
    session.pop('user_id', None)
    return redirect(url_for('login'))


#投稿一覧画面表示
@app.route('/home')
@login_required
def home():
    # 投稿一覧と合わせて投稿者情報も一緒に取得する
    posts = Post.query.options(joinedload(Post.author)).order_by(
        Post.created_at.desc()).all()
    return render_template('home.html', posts=posts)


#ここを修正してもらえると投稿記入欄に飛べる？
@app.route('/posts', methods=['GET', 'POST'])
@login_required #おーちゃん追加2/11
def posts():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form['post_body']
#line226-234おーちゃん追加2/11
        try:
            studytime_hour = int(request.form.get('studytime_hour', 0)) 
            studytime_minutes = int(request.form.get('studytime_minutes', 0))    
        except ValueError:
            studytime_hour = 0 
            studytime_minutes = 0
        total_learning_minutes = (studytime_hour * 60) + studytime_minutes
        if content:
            new_post = Post(content=content, user_id=user_id, learning_time = total_learning_minutes)#おーちゃんlearning_time追加2/11
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('home'))
    return render_template('posts.html')

#本人プロフィール画面表示
@app.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')  # おーちゃん追加
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('login'))
    return render_template('profile.html', post=user)


#他人プロフィール画面表示
@app.route('/others_profile/<int:user_id>')
def others_profile(user_id):
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('home'))
    return render_template('others_profile.html', post=user)


if __name__ == '__main__':
    #本番プロセスのみ起動
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true": 
        #DB作成
        with app.app_context(): 
            db.create_all()
    app.run(host="0.0.0.0", debug=True)
