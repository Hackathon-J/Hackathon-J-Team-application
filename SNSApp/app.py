import time  # おーちゃん追加2/15
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
# SQLAlchemyのrelationshipはdb.relationshipを使うのがいいらしい。
from sqlalchemy.orm import joinedload
from functools import wraps
import re 
#pythonからAWSサービスを操作する道具
import boto3
#アップロードされたファイル名を安全なファイル名に変換するための関数
from werkzeug.utils import secure_filename
#flask-login機能追加
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
#おーちゃん追加2/18　idやuser_idで負の値を許容せず大きな正の値を扱えるようにする
from sqlalchemy.dialects.mysql import INTEGER 
#おーちゃん追加2/18 　SUM,COUNTなどのSQLの集計関数をPython内で使えるようにする
from sqlalchemy import func 

# 定数定義
EMAIL_PATTERN = EMAIL_PATTERN = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
SESSION_DAYS = 30

# Flaskアプリのインスタンス作成
app = Flask(__name__)

#LoginMnagerの初期化
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#セッション設定
app.permanent_session_lifetime = timedelta(days=SESSION_DAYS)
# SQLデータベースの指定
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@db:3306/"
    f"{os.getenv('DB_DATABASE')}"
)
#SQLAlchemyのイベント通知無効化
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#S3クライアントの追加
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION") 
                        )

#コンテナを再起動するたびにセッションが無効かされるので別方法を取る。
#app.config['SECRET_KEY'] = os.urandom(24)
#SECRET_KEYを.envに作成する。
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if app.config['SECRET_KEY'] is None:
    raise RuntimeError("SECRET_KEYが設定されていません。'.env'ファイルを確認してください。")
db = SQLAlchemy(app)

# ログイン「無」確認用デコレータ
def not_logged_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

#データベース共通部分を親クラスとしてまとめた
class BaseModel(db.Model):
    __abstract__ = True #テーブルを作らない

    id = db.Column(INTEGER(unsigned=True), primary_key=True)#おーちゃんunsigned=True追加2/18
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                           onupdate=datetime.utcnow, nullable=False )
    
    #created_atの日本時間変換
    @property
    def created_at_jst(self):
        return self.jst_Change(self.created_at)

    # updated_atの日本時間変換
    @property
    def updated_at_jst(self):
        return self.jst_Change(self.updated_at)

    # 計算式_UTC+9hour
    @staticmethod
    def jst_Change(dt):
        if dt is None:
            return None
        return dt + timedelta(hours=9)

#Userモデル作成
class User(UserMixin, BaseModel):
    __tablename__ = "users"
    
    #ログインIDとして使う
    mailaddress = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=False, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    profile = db.relationship('Profile', backref='user', uselist=False)
    
    def __repr__(self):
        # ユーザーIDもあった方が後で検索とかし易いと思う
        # return f'<User {self.username}>'
        return f'<User id={self.id} username={self.username}>'

    # パスワードの保存(ハッシュ値)
    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256')

    # パスワードの検証
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Postモデル作成
class Post(BaseModel):
    __tablename__ = "posts"
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('users.id'), nullable=False)#おーちゃん変更2/14
    learning_time = db.Column(db.Integer)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'

    @property 
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
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('users.id'), unique=True, nullable=False)
    content = db.Column(db.Text)
    icon_path = db.Column(db.String(255))
    header_path = db.Column(db.String(255))

    def __repr__(self):
        return f'<Profile id={self.id} user_id={self.user_id}>'

#Commentモデル作成
class Comment(BaseModel):
    __tablename__ = "comments"
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('users.id'), nullable=False)  
    post_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('posts.id'), nullable=False)
    def __repr__(self):
        return f'<Comment {self.id} by {self.user_id} on Post {self.post_id}>'

#ルートページのリダイレクト処理
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('home'))

#ログイン画面の表示
@app.route('/login')
def login():
    return render_template('login.html')

#ログイン処理
@app.route('/submit', methods=['POST'])
def submit():
    # request.formは<form>タグから送られてきたデータを扱う。
    mailaddress = request.form['mailaddress']
    password = request.form['password']

    #空チェック
    if not mailaddress or not password:
        return redirect(url_for('login'))
    
    # Flask-SQLAlchemyから引用したqueryプロパティ(SELECT文的な)とfilter_byメソッド(WHERE句的な)
    # 上記をUserクラス(Userテーブル)に適用している。usernameカラムが先ほど定義したusername変数と一致している.first()(LIMIT 1の意味)
    user = User.query.filter_by(mailaddress=mailaddress).first()
    
    if user and user.check_password(password):
        #セッションにuser_idを追加
        login_user(user) # おーちゃん追加
        session.permanent = True  # おーちゃん追加
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

#サインアップページの表示(GET)
@app.route('/signup', methods=['GET'])
@not_logged_required
def signup_view():
    return render_template('signup.html')

# サインアップ処理(POST)
@app.route('/signup', methods=['POST'])
def signup_post():
    username = request.form['username']
    mailaddress = request.form['mailaddress']
    password = request.form['password']
    password_confirmation = request.form['password_confirmation']
    
    if not username or not mailaddress or not password or not password_confirmation:
        return redirect(url_for('signup_view'))
    
    if User.query.filter_by(mailaddress=mailaddress).first():
        return redirect(url_for('signup_view'))
    
    if password != password_confirmation:
        return redirect(url_for('signup_view'))
    
    new_user = User(username=username, mailaddress=mailaddress)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
   
    #ユーザー登録時にProfileも自動で生成する。
    profile = Profile(user_id=new_user.id)
    db.session.add(profile)
    db.session.commit()

    login_user(new_user)
    return redirect(url_for('home'))

#ログアウト処理
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


#投稿一覧画面表示
@app.route('/home')
@login_required
def home():
    #投稿一覧と合わせて投稿者情報も一緒に取得する
    posts = Post.query.options(joinedload(Post.author)).order_by(Post.created_at.desc()).all()
    #ランキングデータの追加　byおーちゃん2/18
    ranking_data = db.session.query(
        User, 
        func.sum(Post.learning_time).label('total_learning_time')
    ).join(Post, User.id == Post.user_id).group_by(
        User.id, User.username 
    ).order_by(
        func.sum(Post.learning_time).desc()
    ).limit(3).all()
    return render_template('home.html', posts=posts, ranking_data=ranking_data)


#投稿記入欄
@app.route('/posts', methods=['GET', 'POST'])
@login_required
def posts():
    if request.method == 'POST':
        content = request.form['post_body']
        try:
            studytime_hour = int(request.form.get('studytime_hour', 0))
            studytime_minutes = int(request.form.get('studytime_minutes', 0))
        except ValueError:
            studytime_hour = 0
            studytime_minutes = 0
        total_learning_minutes = (studytime_hour * 60) + studytime_minutes
        if content:
            new_post = Post(content=content, user_id=current_user.id, learning_time = total_learning_minutes)#おーちゃんlearning_time追加2/11
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('home'))
    return render_template('posts.html')

#本人プロフィール画面表示
@app.route('/profile')
@login_required
def profile():
    return render_template('profile_view.html', target_user=current_user)

#他人プロフィール画面表示
@app.route('/others_profile/<int:user_id>')
@login_required
def others_profile(user_id):
    other_user = User.query.get(user_id)
    if not other_user:
        return redirect(url_for('home'))
    return render_template('profile_view.html', target_user=other_user)

#プロフィール編集
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    profile = current_user.profile

    if request.method == 'POST':
        #表示名
        new_name = request.form.get('username')
        if new_name:
            current_user.username = new_name

        #プロフィール文
        content = request.form.get('content')
        if content is not None:
            profile.content = content
    
        #アイコン画像
        file = request.files.get('icon')
        if file and file.filename:
            #ファイル名を安全なファイル名に変更
            filename = secure_filename(file.filename)

            #S3に保存するパスを作る
            s3_path = f"hackathon_jteam_icons/user_{current_user.id}/{filename}"

            #s3にアップロード
            s3.upload_fileobj(
                file,
                os.getenv("AWS_S3_BUCKET"),
                s3_path,
                ExtraArgs={"ContentType":file.content_type}
            )

            #s3のURL
            file_url = (
                f"https://{os.getenv('AWS_S3_BUCKET')}.s3."
                f"{os.getenv('AWS_S3_REGION')}.amazonaws.com/{s3_path}"
            )

            #DBに保存
            profile.icon_path = file_url
            
        db.session.commit()
        return redirect(url_for('profile'))

    return render_template('profile_edit.html', target_user=current_user)

#投稿詳細画面表示 おーちゃん追加2/18
@app.route('/posts/<int:post_id>')#post_idを受け取る
@login_required
def post_detail(post_id):
    post = Post.query.options(joinedload(Post.author)).get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id).options(joinedload(Comment.author)).order_by(Comment.created_at.asc()).all()
    user_id = current_user.id
    return render_template('post_detail.html', post=post, comments=comments, user_id=user_id)

#コメント投稿用のPOSTルート おーちゃん追加2/18
@app.route('/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.options(joinedload(Post.author)).get_or_404(post_id)
    comments = Comment.query.filter_by(post_id=post_id).options(joinedload(Comment.author)).order_by(Comment.created_at.asc()).all()
    user_id = current_user.id
    if not user_id:
        return redirect(url_for('login'))
    content = request.form['content']
    if not content:
        return redirect(url_for('post_detail', post_id=post_id))
    new_comment = Comment(content=content, user_id=user_id, post_id=post_id)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('post_detail', post_id=post_id))

#コメント削除 おーちゃん追加2/18
@app.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    user_id = current_user.id
    post = Post.query.get_or_404(post_id)
    if post.user_id != user_id:
        return redirect(url_for('home'))
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    #本番プロセスのみ起動
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true": 
        #DB作成 
        with app.app_context(): 
            max_retries = 10
            for i in range(max_retries):
                try:
                    db.create_all()
                    break 
                except Exception as e:
                    if i < max_retries - 1:
                        time.sleep(5) # 
                    else:
                        raise 
    app.run(host="0.0.0.0", debug=True)
