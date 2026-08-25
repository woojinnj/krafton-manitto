from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import random
# db name : krafton_users
# db 요소 : _id uid pwd name mbti want rating targetId
app = Flask(__name__)

client = MongoClient("mongodb://localhost:27017/")
db = client["manitto"]
users = db["users"]
users.create_index("username", unique=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        name=request.form['name']
        want=request.form['want']
        mbti=request.form['mbti']

        if not username or not password or not name or not want or not mbti:
            return render_template(
                'signup.html',
                error='모든 항목을 입력해주세요.'
            )
        
        existing_user=users.find_one({"username":username})
        if existing_user:
            return render_template(
                'signup.html',
                error='이미 존재하는 아이디입니다.'
            )
        
        if len(username)<4:
            return render_template(
                'signup.html',
                error='아이디는 4글자 이상이어야 합니다.'
            )
        
        if len(password)<8:
            return render_template(
                'signup.html',
                error='비밀번호는 8글자 이상이어야 합니다.'
            )

        hashed_password=generate_password_hash(password)

        users.insert_one({
            "username":username,
            "password":hashed_password,
            "name":name,
            "want":want,
            "mbti":mbti,
            "rating_sum":0,
            "rating_count":0
        })

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    user = {
        "name": "국환",
        "mbti": "ENFP",
        "want": "맛있는 간식 주세요"
    }

    ranking = [
        {"name": "이지민", "ranking": 157},
        {"name": "현나", "ranking": 155},
        {"name": "국환", "ranking": 152}
    ]

    return render_template(
        'dashboard.html',
        user=user,
        ranking=ranking
    )
    return render_template('dashboard.html', user=user)

@app.route('/api/shuffle', methods=['POST'])
# 관리자 인증방식 추가
def shuffle():
    # 데이터베이스를 가져오기
    users = list(db.users.find())
    random.shuffle(users)
    n = len(users)

    # 셔플하기 성공
    if(n > 2):
        for i in range(n):
            db.users.update_one(
                {'_id': users[i]['_id']},
                {'$set': {'targetId': users[(i+1)%n]['_id']}}
            )
        return jsonify({'result': 'success'})
    
    # 셔플하기 실패
    return jsonify({'result': 'false'})


if __name__=='__main__':
    app.run(debug=True)