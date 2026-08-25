from flask import Flask, jsonify, render_template
from pymongo import MongoClient
import random

# db name : krafton_users
# db 요소 : _id uid pwd name mbti want rating targetId

app =Flask(__name__)
client = MongoClient("이름 + 로컬 주소입력")
db = client.kraftonUsers

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/shuffle', methods=['POST'])
def api_shuffle():
    # 데이터베이스를 가져오기
    all_users = list(db.KraftonUsers.find())

    # 셔플하기
    for a in 
    return jsonify({'result': 'success'})

if __name__=='__main__':
    app.run(debug=True)