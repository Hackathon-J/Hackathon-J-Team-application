from flask import Flask, render_template


app = Flask(__name__)


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@app.route('/base', methods=['GET'])
def base():
    return render_template('base.html')


@app.route('/posts', methods=['GET'])
def posts():
    return render_template('posts.html')


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
