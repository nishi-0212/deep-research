from .models import Research

_DB: dict[str, Research] = {}  # POC: in memory. Later: SQLite/Postgres.


def save(r: Research):
    _DB[r.id] = r


def get(rid: str) -> Research | None:
    return _DB.get(rid)


def list_for_user(user_id: str) -> list[Research]:
    items = [r for r in _DB.values() if r.user_id == user_id]
    return sorted(items, key=lambda r: r.created_at, reverse=True)