import os  # 追加
from datetime import datetime  # 追加
# requestはインスタンス
from flask import Flask, render_template, request, redirect, url_for, session  # sessionを追加
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, joinedload

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)  # 追加
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    posts = relationship('Post', backref='author', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Post(db.Model):  # 以下7行追加
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Post {self.id} by {self.user_id}>'


with app.app_context():
    db.create_all()


@app.route('/login')
def login():
    return render_template('login.html')


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

    # プログラムでは自動でTrue or Falseを判断できる性質があるので、== Trueなどはいらない
    # つまり if user and user.check_password(password):はuserがあって、パスワードが合っていればとなる
    if user and user.check_password(password):
        # 追加
        session['user_id'] = user.id
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        mailaddress = request.form['mailaddress']
        password = request.form['password']
        password_confirmation = request.form['password_confirmation']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return redirect(url_for('signup'))

        if password != password_confirmation:
            return redirect(url_for('signup'))

        new_user = User(username=username, email=mailaddress)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"新規登録成功: ユーザー '{username}' がデータベースに追加されました。")

        return redirect(url_for('home'))

    return render_template('signup.html')

# 追加


@app.route('/home')
def home():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    posts = Post.query.options(joinedload(Post.author)).order_by(
        Post.created_at.desc()).all()
    return render_template('home.html', posts=posts)


# ここを修正してもらえると投稿記入欄に飛べる？
@app.route('/posts', methods=['GET', 'POST'])
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

# 追加


@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('login'))
    return render_template('profile.html', post=user)


@app.route('/others_profile/<int:user_id>')
def others_profile(user_id):
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('home'))
    return render_template('others_profile.html', post=user)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
