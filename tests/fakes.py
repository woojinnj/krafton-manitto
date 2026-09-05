"""Small MongoDB-compatible fakes used by the regression suite."""

from copy import deepcopy
from dataclasses import dataclass

from pymongo.errors import DuplicateKeyError


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = deepcopy(documents or [])

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _project(document, projection):
        if not projection:
            return deepcopy(document)
        included = {key for key, enabled in projection.items() if enabled and key != "_id"}
        if included:
            result = {key: deepcopy(document[key]) for key in included if key in document}
            if projection.get("_id", 1) and "_id" in document:
                result["_id"] = deepcopy(document["_id"])
            return result
        return {key: deepcopy(value) for key, value in document.items() if projection.get(key, 1)}

    def find_one(self, query, projection=None):
        for document in self.documents:
            if self._matches(document, query):
                return self._project(document, projection)
        return None

    def find(self, query=None, projection=None):
        query = query or {}
        return [
            self._project(document, projection)
            for document in self.documents
            if self._matches(document, query)
        ]

    def insert_one(self, document):
        if "username" in document and self.find_one({"username": document["username"]}):
            raise DuplicateKeyError("duplicate username")
        self.documents.append(deepcopy(document))

    def update_one(self, query, update, upsert=False):
        for document in self.documents:
            if not self._matches(document, query):
                continue
            before = deepcopy(document)
            for key, value in update.get("$set", {}).items():
                document[key] = deepcopy(value)
            for key, value in update.get("$inc", {}).items():
                document[key] = document.get(key, 0) + value
            return UpdateResult(1, int(document != before))

        if upsert:
            document = {key: deepcopy(value) for key, value in query.items() if not isinstance(value, dict)}
            document.update(deepcopy(update.get("$setOnInsert", {})))
            document.update(deepcopy(update.get("$set", {})))
            self.documents.append(document)
            return UpdateResult(0, 0)
        return UpdateResult(0, 0)

    def create_index(self, *args, **kwargs):
        return args[0] if args else "index"


class FakeDatabase:
    def __init__(self, users=None, game_status=None):
        self.collections = {
            "users": FakeCollection(users),
            "game_status": FakeCollection(game_status),
        }

    def __getitem__(self, name):
        return self.collections[name]
