"""HTTP routes for the Manitto game."""

from __future__ import annotations

import random

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash


main = Blueprint("main", __name__)

MBTI_TYPES = {
    "ISTJ", "ISFJ", "INFJ", "INTJ", "ISTP", "ISFP", "INFP", "INTP",
    "ESTP", "ESFP", "ENFP", "ENTP", "ESTJ", "ESFJ", "ENFJ", "ENTJ",
}


def _collections():
    database = current_app.extensions["manitto_db"]
    return database["users"], database["game_status"]


def _signup_error(message: str, values: dict):
    return render_template("signup.html", error=message, **values)


@main.get("/")
def index():
    return render_template("index.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    users, _ = _collections()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = users.find_one({"username": username})

    if not user or not check_password_hash(user.get("password", ""), password):
        return render_template(
            "login.html",
            error="아이디 또는 비밀번호가 올바르지 않습니다.",
            username=username,
        )

    access_token = create_access_token(identity=username)
    response = redirect(url_for("main.dashboard"))
    set_access_cookies(response, access_token)
    return response


@main.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    users, _ = _collections()
    values = {
        "username": request.form.get("username", "").strip(),
        "name": request.form.get("name", "").strip(),
        "want": request.form.get("want", "").strip(),
        "mbti": request.form.get("mbti", "").upper(),
    }
    password = request.form.get("password", "")

    if not all((*values.values(), password)):
        return _signup_error("모든 항목을 입력해주세요.", values)
    if not 4 <= len(values["username"]) <= 20:
        return _signup_error("아이디는 4자 이상 20자 이하여야 합니다.", values)
    if not 8 <= len(password) <= 100:
        return _signup_error("비밀번호는 8자 이상 100자 이하여야 합니다.", values)
    if len(values["name"]) > 20:
        return _signup_error("이름은 20자 이하로 입력해주세요.", values)
    if len(values["want"]) > 100:
        return _signup_error("바라는 점은 100자 이하로 입력해주세요.", values)
    if values["mbti"] not in MBTI_TYPES:
        return _signup_error("올바른 MBTI를 선택해주세요.", values)
    if users.find_one({"username": values["username"]}):
        return _signup_error("이미 존재하는 아이디입니다.", values)

    try:
        users.insert_one(
            {
                **values,
                "password": generate_password_hash(password),
                "rating_sum": 0,
                "rating_count": 0,
                "target_id": None,
                "rated": False,
                "role": "user",
            }
        )
    except DuplicateKeyError:
        return _signup_error("이미 존재하는 아이디입니다.", values)

    return redirect(url_for("main.login"))


@main.route("/logout", methods=["GET", "POST"])
def logout():
    response = redirect(url_for("main.index"))
    unset_jwt_cookies(response)
    return response


@main.get("/dashboard")
@jwt_required()
def dashboard():
    users, _ = _collections()
    username = get_jwt_identity()
    user = users.find_one({"username": username})
    if user is None:
        response = redirect(url_for("main.login"))
        unset_jwt_cookies(response)
        return response

    return render_template(
        "dashboard.html",
        username=username,
        user=user,
        ranking=get_ranking(),
        is_admin=user.get("role") == "admin",
        is_open=get_game_status(),
        mbti_types=sorted(MBTI_TYPES),
    )


@main.post("/api/likes")
@jwt_required()
def likes():
    users, _ = _collections()
    username = get_jwt_identity()
    current_user = users.find_one({"username": username})

    if current_user is None:
        return jsonify(result="false", message="사용자를 찾을 수 없습니다."), 404
    if not get_game_status():
        return jsonify(result="false", message="마니띠 공개 후 별점을 등록할 수 있습니다."), 403
    if current_user.get("target_id") is None:
        return jsonify(result="false", message="아직 마니또가 배정되지 않았습니다.")

    try:
        like = int(request.form.get("like", ""))
    except (TypeError, ValueError):
        return jsonify(result="false", message="별점 형식이 올바르지 않습니다."), 400
    if not 1 <= like <= 5:
        return jsonify(result="false", message="별점은 1점부터 5점까지 가능합니다."), 400

    recipient = users.find_one({"target_id": username}, {"_id": 0, "username": 1})
    if recipient is None:
        return jsonify(result="false", message="별점을 받을 마니띠를 찾을 수 없습니다."), 404

    claim = users.update_one(
        {"username": username, "rated": {"$ne": True}},
        {"$set": {"rated": True}},
    )
    if claim.modified_count == 0:
        return jsonify(result="false", message="이미 별점을 등록했습니다.")

    result = users.update_one(
        {"username": recipient["username"]},
        {"$inc": {"rating_sum": like, "rating_count": 1}},
    )
    if result.matched_count == 0:
        users.update_one({"username": username}, {"$set": {"rated": False}})
        return jsonify(result="false", message="별점을 받을 마니띠를 찾을 수 없습니다."), 404
    return jsonify(result="success")


@main.post("/api/shuffle")
@jwt_required()
def shuffle():
    users, game_status = _collections()
    username = get_jwt_identity()
    if not is_admin(username):
        return jsonify(result="false", message="관리자 권한이 필요합니다."), 403

    user_list = list(users.find({"role": {"$ne": "admin"}}))
    random.shuffle(user_list)
    if len(user_list) < 3:
        return jsonify(result="false", message="마니또 배정에는 최소 3명이 필요합니다."), 400

    for index, user in enumerate(user_list):
        target = user_list[(index + 1) % len(user_list)]
        users.update_one(
            {"username": user["username"]},
            {"$set": {"target_id": target["username"], "rated": False}},
        )
    game_status.update_one(
        {"_id": "current_status"},
        {"$set": {"is_open": False}},
        upsert=True,
    )
    return jsonify(result="success")


@main.post("/api/toggle-open")
@jwt_required()
def toggle_open():
    _, game_status = _collections()
    username = get_jwt_identity()
    if not is_admin(username):
        return jsonify(result="false", message="관리자 권한이 필요합니다."), 403

    new_status = not get_game_status()
    game_status.update_one(
        {"_id": "current_status"},
        {"$set": {"is_open": new_status}},
        upsert=True,
    )
    return jsonify(result="success", is_open=new_status)


@main.get("/dashboard/showManitto")
@jwt_required()
def show_manitto():
    users, _ = _collections()
    username = get_jwt_identity()
    current_user = users.find_one({"username": username})
    if current_user is None:
        return jsonify(result="false", message="사용자를 찾을 수 없습니다."), 404
    if current_user.get("target_id") is None:
        return jsonify(result="false", message="아직 마니또가 배정되지 않았습니다.")

    manitto = users.find_one(
        {"username": current_user["target_id"]},
        {"_id": 0, "name": 1, "mbti": 1, "want": 1},
    )
    if manitto is None:
        return jsonify(result="false", message="마니또 정보를 찾을 수 없습니다."), 404
    return jsonify(result="success", user=manitto)


@main.get("/dashboard/showManitti")
@jwt_required()
def show_manitti():
    users, _ = _collections()
    username = get_jwt_identity()
    if not get_game_status():
        return jsonify(result="false", message="아직 공개되지 않았습니다.")

    current_user = users.find_one({"username": username})
    if current_user is None:
        return jsonify(result="false", message="사용자를 찾을 수 없습니다."), 404
    if current_user.get("target_id") is None:
        return jsonify(result="false", message="아직 마니또가 배정되지 않았습니다.")

    manitti = users.find_one(
        {"target_id": username},
        {"_id": 0, "name": 1, "mbti": 1, "want": 1},
    )
    if manitti is None:
        return jsonify(result="false", message="마니띠 정보를 찾을 수 없습니다."), 404
    return jsonify(result="success", user=manitti, rated=bool(current_user.get("rated")))


@main.get("/dashboard/side/myPage")
@jwt_required()
def my_page():
    users, _ = _collections()
    user = users.find_one(
        {"username": get_jwt_identity()},
        {"_id": 0, "name": 1, "mbti": 1, "rating_sum": 1, "want": 1, "rating_count": 1},
    )
    if user is None:
        return jsonify(result="false", message="사용자를 찾을 수 없습니다."), 404
    count = user.get("rating_count", 0)
    average = user.get("rating_sum", 0) / count if count else 0
    return jsonify(result="success", user=user, avg=average)


@main.put("/dashboard/side/update")
@jwt_required()
def update_user():
    users, _ = _collections()
    update_data = {}

    if "name" in request.form:
        name = request.form["name"].strip()
        if not name or len(name) > 20:
            return jsonify(result="false", message="이름은 1자 이상 20자 이하로 입력해주세요."), 400
        update_data["name"] = name
    if "mbti" in request.form:
        mbti = request.form["mbti"].upper()
        if mbti not in MBTI_TYPES:
            return jsonify(result="false", message="올바른 MBTI를 선택해주세요."), 400
        update_data["mbti"] = mbti
    if "want" in request.form:
        want = request.form["want"].strip()
        if not want or len(want) > 100:
            return jsonify(result="false", message="바라는 점은 1자 이상 100자 이하로 입력해주세요."), 400
        update_data["want"] = want

    if not update_data:
        return jsonify(result="false", message="수정할 정보가 없습니다."), 400
    result = users.update_one(
        {"username": get_jwt_identity()},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        return jsonify(result="false", message="사용자를 찾을 수 없습니다."), 404
    return jsonify(result="success")


def is_admin(username: str) -> bool:
    users, _ = _collections()
    user = users.find_one({"username": username}, {"_id": 0, "role": 1})
    return bool(user and user.get("role") == "admin")


def get_game_status() -> bool:
    _, game_status = _collections()
    status = game_status.find_one({"_id": "current_status"})
    return bool(status and status.get("is_open", False))


def get_ranking() -> list[dict]:
    users, _ = _collections()
    result = []
    for user in users.find(
        {"role": {"$ne": "admin"}},
        {"_id": 0, "name": 1, "rating_sum": 1, "rating_count": 1},
    ):
        count = user.get("rating_count", 0)
        if count <= 0:
            continue
        average = user.get("rating_sum", 0) / count
        result.append({"name": user.get("name", "이름 없음"), "ranking": average, "count": count})
    result.sort(key=lambda item: (-item["ranking"], item["name"]))
    for index, entry in enumerate(result):
        entry["rank"] = (
            result[index - 1]["rank"]
            if index and entry["ranking"] == result[index - 1]["ranking"]
            else index + 1
        )
    return result
