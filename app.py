from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

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
    return render_template('dashboard.html')

@app.route('/api/shuffle', methods=['POST'])
def api_shuffle():
    return jsonify({'result': 'success'})

if __name__=='__main__':
    app.run(debug=True)