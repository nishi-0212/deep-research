from dataclasses import dataclass


@dataclass
class User:
    id: str
    role: str
    blocked_resources: set[str]


# POC users. In Workmate, replace get_user() with the real auth/RBAC lookup.
USERS = {
    "admin": User("admin", "admin", set()),
    "sales": User("sales", "member", {"finance-private"}),
    "intern": User("intern", "member", {"sales-enterprise", "finance-private"}),
}


def get_user(user_id: str) -> User:
    return USERS.get(user_id, USERS["intern"])  # unknown user = least privilege


def can_access(user: User, resource: str) -> bool:
    return resource not in user.blocked_resources