from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    db.create_all()

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/submit', methods = ['POST'])
def submit():
    username = request.form['username']
    password = request.form['password']

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        return redirect(url_for('posts'))
    else:
        return redirect(url_for('login'))

@app.route('/signup', methods = ['GET', 'POST'])
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

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    
    return render_template('signup.html') 

@app.route('/posts')
def posts():
    return render_template('posts.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
