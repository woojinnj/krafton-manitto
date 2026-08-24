from flask import Flask, render_template
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app =Flask(__name__)

client = MongoClient("mongodb://localhost:27017/")
db = client["manitto"]
users = db["users"]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    if request.method=='POST':
        pass
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

if __name__=='__main__':
    app.run(debug=True)