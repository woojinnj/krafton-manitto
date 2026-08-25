from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
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
    return render_template('dashboard.html')

##############################
# 추가기능
##############################

# 좋아요주기
@app.route('/api/likes', methods=['POST'])
def likes():
    user_id = request.form.get('id')

    users = getUserId(user_id)



# 셔플하기
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



##############################
#대시보드 메인화면 기능
##############################

# 마니또 조회하기
@app.route('/dashboard/showManitto', methods=['GET'])
def showManitto():
    user_id = request.form.get('id')

    manitto_doc = db.users.find_one({'targetId': ObjectId(user_id)}) #마니띠 정보

    manitto = getUserId(manitto_doc['_id']) #마니띠

    return jsonify({'result': 'success', 'user': manitto})



# 마니띠 조회하기
@app.route('/dashboard/showManitti', methods=['GET'])
def showManitto():
    user_id = request.form.get('id')

    me = db.users.find_one({'_id': ObjectId(user_id)}) #나의 정보

    manitti = getUserId(me['targetId']) #마니띠

    return jsonify({'result': 'success', 'user': manitti})



##############################
#사이드바 기능
##############################

# 마이페이지 보기
@app.route('/dashboard/side/myPage')
def myPage():
    user_id = request.form.get('id')
    user = db.users.find_one(
            {'_id':ObjectId(user_id)},
            {'_id':0, 'name':1, 'mbti':1, 'rating_sum':1, 'want':1} # id를 제외하고 리턴
        )
    return jsonify({'result': 'success', 'user': user})

# 정보 업데이트
@app.route('dashboard/side/update', methods=['POST'])
def update_user():
    user_id = request.form.get('id')
    
    # 들어온 값만 dictionary
    update_data = {}
    if 'name' in request.form: update_data['name'] = request.form['name']
    if 'mbti' in request.form: update_data['mbti'] = request.form['mbti']
    if 'want' in request.form: update_data['want'] = request.form['want']

    # update_data에 포함된 필드만 수정
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
    return jsonify({'result': 'success'})




####################
# 유틸 함수
####################

#id를 받아 유저 호출
def getUserId(user_id):
    return db.users.find_one(
        {'_id': ObjectId(user_id)},
        {'_id': 0, 'password': 0, 'targetId': 0, 'name': 1, 'mbti': 1, 'rating_sum': 1, 'want': 1}
    )







# 더미데이터 테스트
# @app.route('/api/dummy')
# def make_dummy():
#     db.users.delete_many({})

#     dummy_users = [
#         {"username": "test1", "name": "핑구", "want": "커피 사주기", "mbti": "INTP"},
#         {"username": "test2", "name": "핑가", "want": "칭찬 많이", "mbti": "ENFP"},
#         {"username": "test3", "name": "핑고", "want": "간식 챙기기", "mbti": "ISTJ"},
#         {"username": "test4", "name": "핑조", "want": "손편지", "mbti": "ESFJ"},
#         {"username": "test5", "name": "핑수", "want": "같이 산책", "mbti": "INFP"},
#     ]
#     for u in dummy_users:
#         u["password"] = generate_password_hash("1234")  # 회원가입에도 쓰는 해시 함수
#         u["rating_sum"] = 0
#         u["rating_count"] = 0
#         u["targetId"] = None

#     db.users.insert_many(dummy_users)   # 5명 한 번에 삽입
#     return jsonify({"result": "success", "inserted": len(dummy_users)})

if __name__=='__main__':
    app.run(debug=True)