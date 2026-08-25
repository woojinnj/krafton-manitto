import random

from bson.objectid import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
)
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = (
    "QO0mteoUjLG0KRAFTONJUNGLELETSGOhF7w2Y7fGLLIIXZ6yMq5ItK30"  # .env 환경변수 파일에 넣어야함. 이렇게 하면 유출 가능성 있음
)
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_HTTPONLY"] = True

jwt = JWTManager(app)

client = MongoClient("mongodb://localhost:27017/")
db = client["manitto"]
users = db["users"]
users.create_index("username", unique=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users.find_one({"username": username})
        
        if user and check_password_hash(user["password"], password):
            access_token = create_access_token(identity=username)
            response = redirect(url_for("dashboard"))
            set_access_cookies(response, access_token)
            return response
        
        else:
            return render_template(
                'login.html',
                error="아이디 또는 비밀번호가 올바르지 않습니다."
            )
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        name = request.form["name"]
        want = request.form["want"]
        mbti = request.form["mbti"]

        if not username or not password or not name or not want or not mbti:
            return render_template("signup.html", error="모든 항목을 입력해주세요.")

        existing_user = users.find_one({"username": username})
        if existing_user:
            return render_template("signup.html", error="이미 존재하는 아이디입니다.")

        if len(username) < 4:
            return render_template(
                "signup.html", error="아이디는 4글자 이상이어야 합니다."
            )

        if len(password) < 8:
            return render_template(
                "signup.html", error="비밀번호는 8글자 이상이어야 합니다."
            )

        hashed_password = generate_password_hash(password)

        users.insert_one(
            {
                "username": username,
                "password": hashed_password,
                "name": name,
                "want": want,
                "mbti": mbti,
                "rating_sum": 0,
                "rating_count": 0,
            }
        )

        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/dashboard")
@jwt_required()
def dashboard():
    username=get_jwt_identity()
    return render_template("dashboard.html",username=username)


##############################
# 추가기능
##############################

# 좋아요 주기 /success
@app.route('/api/likes', methods=['POST'])
def likes():
    like = int(request.form.get('like'))
    user_id = request.form.get('id')
    # 5보다 작게 받기 추가해야함
    me = db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc":{
            "rating_sum": like, 
            "rating_count": 1
            }}
    ) #나의 정보

    return jsonify({"result":"success"})

# 정렬하기
@app.route('/api/sort', methods=['POST'])
def sort():
    userList = list(users.find({}, {'_id' : 0 , 'name':1, 'rating_sum': 1, 'rating_count':1}))
    
    ranker = []
    for user in userList:
        name = user.get('name')
        if user.get('rating_count', 0) != 0:
            avg = user.get('rating_sum', 0) / user.get('rating_count', 0)
            ranker.append({'name': name, 'avg': avg})

    ranker.sort(key=lambda x: x['avg'], reverse=True) #파이썬 정렬 함수

    return ranker[:5]

    

# 셔플하기 /success
@app.route('/api/shuffle', methods=['POST'])
# 관리자 인증방식 추가
def shuffle():
    # 데이터베이스를 가져오기
    userList = list(users.find())
    random.shuffle(userList)
    n = len(userList)

    # 셔플하기 성공
    if n > 2:
        for i in range(n):
            db.users.update_one(
                {"_id": userList[i]["_id"]},
                {"$set": {"targetId": userList[(i + 1) % n]["_id"]}},
            )
        return jsonify({"result": "success"})

    # 셔플하기 실패
    return jsonify({"result": "false"})

##############################
#대시보드 메인화면 기능
##############################

# 마니또 조회하기
@app.route('/dashboard/showManitto', methods=['GET'])
def showManitto():
    user_id = request.args.get('id')

    manitto_doc = users.find_one({'targetId': ObjectId(user_id)}) #마니띠 정보

    manitto = getUserId(manitto_doc['_id']) #마니띠

    return jsonify({'result': 'success', 'user': manitto})



# 마니띠 조회하기
@app.route('/dashboard/showManitti', methods=['GET'])
def showManitti():
    user_id = request.args.get('id')

    me = users.find_one({'_id': ObjectId(user_id)}) #나의 정보

    manitti = getUserId(me['targetId']) #마니띠

    return jsonify({'result': 'success', 'user': manitti})



##############################
#사이드바 기능
##############################

# 마이페이지 보기
@app.route('/dashboard/side/myPage', methods=['POST'])
def myPage():
    user_id = request.form.get('id')
    user = users.find_one(
            {'_id':ObjectId(user_id)},
            {'_id':0, 'name':1, 'mbti':1, 'rating_sum':1, 'want':1} # id를 제외하고 리턴
        )
    return jsonify({'result': 'success', 'user': user})

# 정보 업데이트
@app.route('/dashboard/side/update', methods=['POST'])
def update_user():
    user_id = request.form.get('id')
    
    # 들어온 값만 dictionary
    update_data = {}
    if 'name' in request.form: update_data['name'] = request.form['name']
    if 'mbti' in request.form: update_data['mbti'] = request.form['mbti']
    if 'want' in request.form: update_data['want'] = request.form['want']

    # update_data에 포함된 필드만 수정
    users.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
    return jsonify({'result': 'success'})

####################
# 유틸 함수
####################

#id를 받아 유저 호출
def getUserId(user_id):
    return db.users.find_one(
        {'_id': ObjectId(user_id)},
        {'_id': 0, 'name': 1, 'mbti': 1, 'rating_sum': 1, 'want': 1}
    )

# 점수 평균 함수
def averageRating(user_id):
    user = users.find_one({"_id":ObjectId(user_id)})

    if not user:
        return 0.0

    sum = user.get("rating_sum", 0) # 기본 0
    count = user.get("rating_count",0)

    return round(sum/count, 2)








# 더미데이터 테스트
# @app.route('/api/dummy')
# def make_dummy():
#     users.delete_many({})

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

#     users.insert_many(dummy_users)   # 5명 한 번에 삽입
#     return jsonify({"result": "success", "inserted": len(dummy_users)})

if __name__=='__main__':
    app.run(debug=True)
