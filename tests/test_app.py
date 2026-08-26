import importlib
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pymongo
from werkzeug.security import generate_password_hash


class FakeCollection:
    def __init__(self):
        self.documents = []

    def create_index(self, *_args, **_kwargs):
        return None

    def delete_many(self, _query):
        self.documents.clear()

    def insert_one(self, document):
        self.documents.append(deepcopy(document))
        return SimpleNamespace(inserted_id=len(self.documents))

    def find(self, query=None, projection=None):
        return [
            self._project(document, projection)
            for document in self.documents
            if self._matches(document, query or {})
        ]

    def find_one(self, query, projection=None):
        for document in self.documents:
            if self._matches(document, query):
                return self._project(document, projection)
        return None

    def update_one(self, query, update, upsert=False):
        for document in self.documents:
            if not self._matches(document, query):
                continue

            for key, value in update.get("$set", {}).items():
                document[key] = value
            for key, value in update.get("$inc", {}).items():
                document[key] = document.get(key, 0) + value
            return SimpleNamespace(matched_count=1)

        if upsert:
            document = deepcopy(query)
            document.update(update.get("$set", {}))
            self.documents.append(document)
            return SimpleNamespace(matched_count=0)

        return SimpleNamespace(matched_count=0)

    @staticmethod
    def _matches(document, query):
        return all(document.get(key) == value for key, value in query.items())

    @staticmethod
    def _project(document, projection):
        if projection is None:
            return deepcopy(document)

        included = {key for key, value in projection.items() if value and key != "_id"}
        if included:
            return {key: deepcopy(document[key]) for key in included if key in document}

        result = deepcopy(document)
        for key, value in projection.items():
            if not value:
                result.pop(key, None)
        return result


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())

    def __getattr__(self, name):
        return self[name]


class FakeMongoClient:
    def __init__(self, *_args, **_kwargs):
        self.databases = {}

    def __getitem__(self, name):
        return self.databases.setdefault(name, FakeDatabase())


with patch.object(pymongo, "MongoClient", FakeMongoClient):
    app_module = importlib.import_module("app")


class ManittoAppTestCase(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True)
        app_module.users.delete_many({})
        app_module.game_status.delete_many({})
        self.client = app_module.app.test_client()

    def add_user(self, username, role="user", target_id=None, rated=False):
        app_module.users.insert_one(
            {
                "username": username,
                "password": generate_password_hash("password123"),
                "name": username.upper(),
                "want": "coffee",
                "mbti": "INTJ",
                "rating_sum": 0,
                "rating_count": 0,
                "target_id": target_id,
                "rated": rated,
                "role": role,
            }
        )

    def login(self, username):
        response = self.client.post(
            "/login",
            data={"username": username, "password": "password123"},
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_and_game_flow(self):
        self.add_user("admin", role="admin", rated=True)
        self.add_user("alice", rated=True)
        self.add_user("bob", rated=True)
        self.login("admin")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("관리자 제어판", dashboard.get_data(as_text=True))

        shuffled = self.client.post("/api/shuffle")
        self.assertEqual(shuffled.status_code, 200)
        self.assertEqual(shuffled.get_json()["result"], "success")

        users = app_module.users.find()
        usernames = {user["username"] for user in users}
        self.assertEqual({user["target_id"] for user in users}, usernames)
        self.assertTrue(all(user["target_id"] != user["username"] for user in users))
        self.assertTrue(all(user["rated"] is False for user in users))
        self.assertFalse(app_module.get_game_status())

        toggled = self.client.post("/api/toggle-open")
        self.assertEqual(toggled.status_code, 200)
        self.assertTrue(toggled.get_json()["is_open"])

        manitto = self.client.get("/dashboard/showManitto")
        manitti = self.client.get("/dashboard/showManitti")
        self.assertEqual(manitto.get_json()["result"], "success")
        self.assertEqual(manitti.get_json()["result"], "success")

    def test_non_admin_cannot_shuffle_or_toggle(self):
        self.add_user("alice")
        self.login("alice")

        dashboard = self.client.get("/dashboard")
        self.assertNotIn("관리자 제어판", dashboard.get_data(as_text=True))
        self.assertEqual(self.client.post("/api/shuffle").status_code, 403)
        self.assertEqual(self.client.post("/api/toggle-open").status_code, 403)

    def test_rating_can_only_be_submitted_once(self):
        self.add_user("alice", target_id="bob")
        self.add_user("bob", target_id="charlie")
        self.add_user("charlie", target_id="alice")
        self.login("alice")

        first = self.client.post("/api/likes", data={"like": "5"})
        second = self.client.post("/api/likes", data={"like": "4"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.get_json()["result"], "false")
        recipient = app_module.users.find_one({"username": "charlie"})
        self.assertEqual(recipient["rating_sum"], 5)
        self.assertEqual(recipient["rating_count"], 1)

    def test_signup_creates_regular_user(self):
        response = self.client.post(
            "/signup",
            data={
                "username": "newuser",
                "password": "password123",
                "name": "New User",
                "want": "book",
                "mbti": "ENFP",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = app_module.users.find_one({"username": "newuser"})
        self.assertEqual(user["role"], "user")
        self.assertFalse(user["rated"])


if __name__ == "__main__":
    unittest.main()
