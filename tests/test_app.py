import unittest

from werkzeug.security import generate_password_hash

from manitto import create_app
from tests.fakes import FakeDatabase


class ManittoAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = generate_password_hash("password123")

    def setUp(self):
        common = {
            "password": self.password_hash,
            "rating_sum": 0,
            "rating_count": 0,
            "rated": False,
            "want": "커피 한 잔 건네주세요",
        }
        self.database = FakeDatabase(
            users=[
                {**common, "username": "admin", "name": "관리자", "mbti": "ENTJ", "role": "admin", "target_id": None},
                {**common, "username": "alice", "name": "앨리스", "mbti": "ENFP", "role": "user", "target_id": "bob12"},
                {**common, "username": "bob12", "name": "밥", "mbti": "ISTJ", "role": "user", "target_id": "carol"},
                {**common, "username": "carol", "name": "캐럴", "mbti": "INFJ", "role": "user", "target_id": "alice"},
            ],
            game_status=[{"_id": "current_status", "is_open": False}],
        )
        self.app = create_app(
            {
                "TESTING": True,
                "JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes",
                "JWT_COOKIE_SECURE": False,
            },
            self.database,
        )
        self.client = self.app.test_client()

    def login(self, username="alice", client=None):
        client = client or self.client
        response = client.post(
            "/login",
            data={"username": username, "password": "password123"},
        )
        self.assertEqual(response.status_code, 302)
        return client

    @staticmethod
    def csrf_headers(client):
        cookie = client.get_cookie("csrf_access_token")
        return {"X-CSRF-TOKEN": cookie.value}

    def test_public_pages_and_security_headers(self):
        for path in ("/", "/login", "/signup"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_production_rejects_the_development_secret(self):
        with self.assertRaises(RuntimeError):
            create_app({"MANITTO_ENV": "production"}, FakeDatabase())

    def test_dashboard_requires_login_then_renders_profile(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

        self.login()
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("앨리스".encode(), response.data)

    def test_signup_validates_and_creates_user(self):
        response = self.client.post(
            "/signup",
            data={"username": "new1", "password": "short", "name": "새싹", "mbti": "ENFP", "want": "응원"},
        )
        self.assertIn("8자 이상 100자 이하".encode(), response.data)

        response = self.client.post(
            "/signup",
            data={"username": "new1", "password": "securepass", "name": "새싹", "mbti": "ENFP", "want": "응원"},
        )
        self.assertEqual(response.status_code, 302)
        created = self.database["users"].find_one({"username": "new1"})
        self.assertEqual(created["role"], "user")
        self.assertNotEqual(created["password"], "securepass")

    def test_assignment_visibility_and_admin_permissions(self):
        self.login()
        response = self.client.get("/dashboard/showManitto")
        self.assertEqual(response.json["user"]["name"], "밥")
        self.assertEqual(self.client.get("/dashboard/showManitti").json["result"], "false")
        forbidden = self.client.post("/api/shuffle", headers=self.csrf_headers(self.client))
        self.assertEqual(forbidden.status_code, 403)

        admin_client = self.app.test_client()
        self.login("admin", admin_client)
        headers = self.csrf_headers(admin_client)
        opened = admin_client.post("/api/toggle-open", headers=headers)
        self.assertTrue(opened.json["is_open"])
        self.assertEqual(self.client.get("/dashboard/showManitti").json["user"]["name"], "캐럴")

        shuffled = admin_client.post("/api/shuffle", headers=headers)
        self.assertEqual(shuffled.json["result"], "success")
        users = self.database["users"].find({"role": {"$ne": "admin"}})
        self.assertTrue(all(user["target_id"] != user["username"] for user in users))
        self.assertEqual(len({user["target_id"] for user in users}), 3)

    def test_rating_is_applied_once_to_the_manitti(self):
        self.database["game_status"].update_one(
            {"_id": "current_status"}, {"$set": {"is_open": True}}
        )
        self.login()
        headers = self.csrf_headers(self.client)
        response = self.client.post("/api/likes", data={"like": "5"}, headers=headers)
        self.assertEqual(response.json["result"], "success")
        recipient = self.database["users"].find_one({"username": "carol"})
        self.assertEqual((recipient["rating_sum"], recipient["rating_count"]), (5, 1))

        revealed = self.client.get("/dashboard/showManitti")
        self.assertTrue(revealed.json["rated"])

        repeated = self.client.post("/api/likes", data={"like": "4"}, headers=headers)
        self.assertEqual(repeated.json["message"], "이미 별점을 등록했습니다.")
        recipient = self.database["users"].find_one({"username": "carol"})
        self.assertEqual((recipient["rating_sum"], recipient["rating_count"]), (5, 1))

    def test_rating_before_reveal_cannot_change_scores(self):
        self.login()
        response = self.client.post(
            "/api/likes", data={"like": "5"}, headers=self.csrf_headers(self.client)
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.database["users"].find_one({"username": "alice"})["rated"])
        self.assertEqual(self.database["users"].find_one({"username": "carol"})["rating_count"], 0)

    def test_ranking_omits_unrated_users_and_shares_equal_ranks(self):
        from manitto.routes import get_ranking

        with self.app.app_context():
            self.assertEqual(get_ranking(), [])
            for username, score, count in [("alice", 10, 2), ("bob12", 5, 1), ("carol", 4, 1)]:
                self.database["users"].update_one(
                    {"username": username}, {"$set": {"rating_sum": score, "rating_count": count}}
                )
            ranking = get_ranking()
            self.assertEqual([user["rank"] for user in ranking], [1, 1, 3])
            self.assertEqual([user["ranking"] for user in ranking], [5, 5, 4])

    def test_sensitive_pages_are_not_cached(self):
        self.login()
        for path in ("/dashboard", "/dashboard/showManitto", "/dashboard/side/myPage"):
            response = self.client.get(path)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_profile_rejects_missing_csrf_and_preserves_data(self):
        self.login()
        response = self.client.put("/dashboard/side/update", data={"name": "변경"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.database["users"].find_one({"username": "alice"})["name"], "앨리스")

    def test_profile_update_rejects_partial_invalid_and_ignores_privileged_fields(self):
        self.login()
        headers = self.csrf_headers(self.client)
        for values in ({"name": "변경", "want": " "}, {"want": "a" * 101}, {"name": "a" * 21}):
            response = self.client.put("/dashboard/side/update", data=values, headers=headers)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.database["users"].find_one({"username": "alice"})["name"], "앨리스")
        response = self.client.put("/dashboard/side/update", data={"name": "새이름", "role": "admin"}, headers=headers)
        self.assertEqual(response.json["result"], "success")
        self.assertEqual(self.database["users"].find_one({"username": "alice"})["role"], "user")

    def test_profile_update_validation_and_update(self):
        self.login()
        headers = self.csrf_headers(self.client)
        invalid = self.client.put("/dashboard/side/update", data={"mbti": "NOPE"}, headers=headers)
        self.assertEqual(invalid.status_code, 400)

        updated = self.client.put(
            "/dashboard/side/update",
            data={"name": "새이름", "mbti": "INTP", "want": "간식"},
            headers=headers,
        )
        self.assertEqual(updated.json["result"], "success")
        user = self.database["users"].find_one({"username": "alice"})
        self.assertEqual((user["name"], user["mbti"], user["want"]), ("새이름", "INTP", "간식"))


if __name__ == "__main__":
    unittest.main()
