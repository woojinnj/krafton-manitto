import random

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = (
    "QO0mteoUjLG0KRAFTONJUNGLELETSGOhF7w2Y7fGLLIIXZ6yMq5ItK30"  # .env 환경변수 파일에 넣어야함. 이렇게 하면 유출 가능성 있음
)
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_HTTPONLY"] = True
app.config["JWT_COOKIE_CSRF_PROTECT"] = False

jwt = JWTManager(app)

client = MongoClient("mongodb://localhost:27017/")
db = client["manitto"]
users = db["users"]
users.create_index("username", unique=True)

game_status = db["game_status"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            access_token = create_access_token(identity=username)
            response = redirect(url_for("dashboard"))
            set_access_cookies(response, access_token)
            return response

        else:
            return render_template(
                "login.html", error="아이디 또는 비밀번호가 올바르지 않습니다."
            )
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        name = request.form.get("name")
        want = request.form.get("want")
        mbti = request.form.get("mbti")

        if not username or not password or not name or not want or not mbti:
            return render_template(
                "signup.html",
                error="모든 항목을 입력해주세요.",
                username=username,
                name=name,
                mbti=mbti,
                want=want,
            )

        existing_user = users.find_one({"username": username})
        if existing_user:
            return render_template(
                "signup.html",
                error="이미 존재하는 아이디입니다.",
                username=username,
                name=name,
                mbti=mbti,
                want=want,
            )

        if len(username) < 4:
            return render_template(
                "signup.html",
                error="아이디는 4글자 이상이어야 합니다.",
                username=username,
                name=name,
                mbti=mbti,
                want=want,
            )

        if len(password) < 8:
            return render_template(
                "signup.html",
                error="비밀번호는 8글자 이상이어야 합니다.",
                username=username,
                name=name,
                mbti=mbti,
                want=want,
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
                "target_id": None,
                "rated": False,
                "role": "user",
            }
        )

        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    response = redirect(url_for("index"))
    unset_jwt_cookies(response)
    return response

@app.route("/dashboard")
@jwt_required()
def dashboard():
    username = get_jwt_identity()

    user = users.find_one({"username": username})
    if user is None:
        response = redirect(url_for("login"))
        unset_jwt_cookies(response)
        return response

    return render_template(
        "dashboard.html",
        username=username,
        user=user,
        ranking=ranking(),
        is_admin=is_admin(username),
        is_open=get_game_status(),
    )


##############################
# 기능
##############################


# 좋아요 주기 / 수정중 / JWT로 수정
@app.route("/api/likes", methods=["POST"])
@jwt_required()
def likes():
    username = get_jwt_identity()
    current_user = users.find_one({"username": username})

    if current_user is None:
        return jsonify({"result": "false", "message": "사용자를 찾을 수 없습니다."}), 404

    if current_user.get("target_id") is None:
        return jsonify(
            {"result": "false", "message": "아직 마니또가 배정되지 않았습니다."}
        )

    # 이미 별점을 줬는지 확인
    if current_user.get("rated", False):
        return jsonify({"result": "false", "message": "이미 별점을 등록했습니다."})

    try:
        like = int(request.form.get("like"))
    except (TypeError, ValueError):
        return jsonify({"result": "false", "message": "별점 형식이 올바르지 않습니다."}), 400

    if 1 <= like <= 5:
        # 나를 마니또로 배정받은 사용자(내 마니띠)에게 별점 추가
        result = users.update_one(
            {"target_id": username},
            {"$inc": {"rating_sum": like, "rating_count": 1}},
        )

        if result.matched_count == 0:
            return jsonify(
                {"result": "false", "message": "별점을 받을 마니띠를 찾을 수 없습니다."}
            ), 404

        # 나는 별점을 줬다고 표시
        users.update_one(
            {"username": username},
            {"$set": {"rated": True}},
        )

        return jsonify({"result": "success"})

    return jsonify({"result": "false", "message": "별점은 1점부터 5점까지 가능합니다."}), 400

# 셔플하기 / success
@app.route("/api/shuffle", methods=["POST"])
@jwt_required()
def shuffle():
    username = get_jwt_identity()

    if not is_admin(username):
        return jsonify({"result": "false", "message": "관리자 권한이 필요합니다."}), 403

    user_list = list(users.find())
    random.shuffle(user_list)
    n = len(user_list)

    if n > 2:
        for i in range(n):
            users.update_one(
                {"username": user_list[i]["username"]},
                {
                    "$set": {
                        "target_id": user_list[(i + 1) % n]["username"],
                        "rated": False,
                    }
                },
            )
        game_status.update_one(
            {"_id": "current_status"},
            {"$set": {"is_open": False}},
            upsert=True,
        )
        return jsonify({"result": "success"})

    return jsonify(
        {"result": "false", "message": "마니또 배정에는 최소 3명이 필요합니다."}
    ), 400

# 마니또 공개 토글 / success
@app.route("/api/toggle-open", methods=["POST"])
@jwt_required()
def toggle_open():
    username = get_jwt_identity()

    if not is_admin(username):
        return jsonify({"result": "false", "message": "관리자 권한이 필요합니다."}), 403

    new_status = not get_game_status()
    game_status.update_one(
        {"_id": "current_status"},
        {"$set": {"is_open": new_status}},
        upsert=True,
    )

    return jsonify({"result": "success", "is_open": new_status})


##############################
# 대시보드 메인화면 기능
##############################


# 마니또 조회하기 / success
@app.route("/dashboard/showManitto", methods=["GET"])
@jwt_required()
def showManitto():
    username = get_jwt_identity()
    if not get_game_status():
        return jsonify({"result": "false", "message": "아직 공개되지 않았습니다."})

    current_user = users.find_one({"username": username})

    if current_user is None:
        return jsonify({"result": "false", "message": "사용자를 찾을 수 없습니다."}), 404

    if current_user.get("target_id") is None:
        return jsonify(
            {"result": "false", "message": "아직 마니또가 배정되지 않았습니다."}
        )

    manitto = users.find_one(
        {"username": current_user["target_id"]},
        {"_id": 0, "name": 1, "mbti": 1, "want": 1},
    )

    if manitto is None:
        return jsonify({"result": "false", "message": "마니또 정보를 찾을 수 없습니다."}), 404

    return jsonify({"result": "success", "user": manitto})

# 마니띠 조회하기 / success
@app.route("/dashboard/showManitti", methods=["GET"])
@jwt_required()
def showManitti():
    username = get_jwt_identity()
    if not get_game_status():
        return jsonify({"result": "false", "message": "아직 공개되지 않았습니다."})

    current_user = users.find_one({"username": username})

    if current_user is None:
        return jsonify({"result": "false", "message": "사용자를 찾을 수 없습니다."}), 404

    if current_user.get("target_id") is None:
        return jsonify(
            {"result": "false", "message": "아직 마니또가 배정되지 않았습니다."}
        )

    manitti = users.find_one(
        {"target_id": username},
        {"_id": 0, "name": 1, "mbti": 1, "want": 1},
    )

    if manitti is None:
        return jsonify({"result": "false", "message": "마니띠 정보를 찾을 수 없습니다."}), 404

    return jsonify({"result": "success", "user": manitti})


##############################
# 사이드바 기능
##############################


# 마이페이지 보기 / success
@app.route("/dashboard/side/myPage", methods=["GET"])
@jwt_required()
def myPage():
    username = get_jwt_identity()
    user = users.find_one(
        {"username": username},
        {"_id": 0, "name": 1, "mbti": 1, "rating_sum": 1, "want": 1, "rating_count": 1},
    )

    count = user.get("rating_count", 0)
    if count == 0:
        avg = 0
    else:
        avg = user.get("rating_sum", 0) / count

    return jsonify({"result": "success", "user": user, "avg": avg})


# 정보 업데이트 / success
@app.route("/dashboard/side/update", methods=["PUT"])
@jwt_required()
def update_user():
    username = get_jwt_identity()

    # 들어온 값만 dictionary
    update_data = {}
    if "name" in request.form:
        update_data["name"] = request.form["name"]
    if "mbti" in request.form:
        update_data["mbti"] = request.form["mbti"]
    if "want" in request.form:
        update_data["want"] = request.form["want"]

    if not update_data:
        return jsonify({"result": "false", "message": "수정할 정보가 없습니다."}), 400

    # update_data에 포함된 필드만 수정
    users.update_one({"username": username}, {"$set": update_data})
    return jsonify({"result": "success"})


####################
# 유틸 함수
####################

# 타겟 / succcess
def get_target(username):
    user = users.find_one({"username": username}, {"_id": 0, "target_id": 1})
    if user is None:
        return None
    return user.get("target_id")

# 유저타입 / success
def is_admin(username):
    user = users.find_one({"username": username}, {"_id": 0, "role": 1})
    return bool(user and user.get("role") == "admin")

# 랭킹함수 / success
def ranking():
    user_list = list(
        users.find({}, {"_id": 0, "name": 1, "rating_sum": 1, "rating_count": 1})
    )
    
    ranking = []
    
    for rank_user in user_list:
        rating_sum = rank_user.get("rating_sum", 0)
        rating_count = rank_user.get("rating_count", 0)
    
        if rating_count == 0:
            avg = 0
        else:
            avg = rating_sum / rating_count
    
        ranking.append({"name": rank_user.get("name", "이름 없음"), "ranking": avg})
    
    ranking.sort(key=lambda x: x["ranking"], reverse=True)

    return ranking

# 게임 상태 초기 설정 / success
def init_game_status():
    status = game_status.find_one({"_id": "current_status"})
    if status is None:
        game_status.insert_one({"_id": "current_status", "is_open": False})
        return None
    return status

# 게임 상태 조회
def get_game_status():
    status = game_status.find_one({"_id": "current_status"})
    if status is None:
        return False
    return status.get("is_open", False)


# # 더미테스트
# @app.route("/api/dummy")
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
#         u["target_id"] = None

#     users.insert_many(dummy_users)   # 5명 한 번에 삽입
#     return jsonify({"result": "success", "inserted": len(dummy_users)})

if __name__ == "__main__":
    app.run(debug=True)
