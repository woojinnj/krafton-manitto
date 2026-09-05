"""Application factory for the Manitto service."""

from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask, jsonify, redirect, request, url_for
from flask_jwt_extended import JWTManager
from pymongo import MongoClient

from .routes import main


jwt = JWTManager()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def create_app(test_config: dict | None = None, database=None) -> Flask:
    """Create a configured app, optionally with an injected test database."""

    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )
    environment = os.getenv("MANITTO_ENV", "development")
    development_secret = "manitto-local-development-only-secret"
    secret_key = os.getenv("JWT_SECRET_KEY", development_secret)

    app.config.from_mapping(
        MANITTO_ENV=environment,
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
        MONGO_DB_NAME=os.getenv("MONGO_DB_NAME", "manitto"),
        JWT_SECRET_KEY=secret_key,
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=12),
        JWT_COOKIE_HTTPONLY=True,
        JWT_COOKIE_CSRF_PROTECT=True,
        JWT_COOKIE_SAMESITE="Lax",
        JWT_COOKIE_SECURE=_env_bool("JWT_COOKIE_SECURE", environment == "production"),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    if (
        app.config["MANITTO_ENV"] == "production"
        and app.config["JWT_SECRET_KEY"] == development_secret
    ):
        raise RuntimeError("JWT_SECRET_KEY must be set in production")

    jwt.init_app(app)
    if database is None:
        mongo_client = MongoClient(
            app.config["MONGO_URI"],
            connect=False,
            serverSelectionTimeoutMS=3_000,
        )
        database = mongo_client[app.config["MONGO_DB_NAME"]]
        app.extensions["mongo_client"] = mongo_client

    app.extensions["manitto_db"] = database
    app.register_blueprint(main)
    _register_auth_handlers(app)
    _register_security_headers(app)
    _register_commands(app)
    return app


def _register_auth_handlers(app: Flask) -> None:
    @jwt.unauthorized_loader
    def unauthorized(reason: str):
        if request.endpoint == "main.dashboard":
            return redirect(url_for("main.login", next=request.path))
        return jsonify(result="false", message="로그인이 필요합니다."), 401

    @jwt.invalid_token_loader
    def invalid_token(reason: str):
        if request.endpoint == "main.dashboard":
            return redirect(url_for("main.login"))
        return jsonify(result="false", message="인증 정보가 올바르지 않습니다."), 422

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        if request.endpoint == "main.dashboard":
            return redirect(url_for("main.login"))
        return jsonify(result="false", message="로그인이 만료되었습니다."), 401


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def add_security_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        return response


def _register_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create the indexes required by the application."""

        database = app.extensions["manitto_db"]
        database["users"].create_index("username", unique=True)
        database["users"].create_index("target_id")
        database["game_status"].update_one(
            {"_id": "current_status"},
            {"$setOnInsert": {"is_open": False}},
            upsert=True,
        )
        print("Database initialized.")
