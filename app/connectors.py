import re
from .models import Evidence
from .rbac import User, can_access
from .seed_data import DATA

STOP = {"the", "and", "for", "our", "are", "was", "with", "that", "this",
        "from", "did", "why", "how", "what", "you", "has", "have"}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:5] for w in words if len(w) > 2 and w not in STOP}


class Connector:
    name = "base"

    def search(self, query: str, user: User, limit: int = 5) -> list[Evidence]:
        raise NotImplementedError


class MockConnector(Connector):
    """Keyword search over seed data. RBAC is applied INSIDE the search."""

    def __init__(self, name: str):
        self.name = name

    def search(self, query, user, limit=5):
        q = _tokens(query)
        results = []
        for d in DATA:
            if d["source"] != self.name:
                continue
            if not can_access(user, d["resource"]):
                continue
            overlap = len(q & _tokens(d["text"]))
            if overlap == 0:
                continue
            results.append(Evidence(
                source_type=self.name, reference=d["resource"], date=d["date"],
                snippet=d["text"], url=d["url"], research_area="",
                score=round(overlap / max(len(q), 1), 2),
            ))
        results.sort(key=lambda e: e.score, reverse=True)
        return results[:limit]


REGISTRY: dict[str, Connector] = {
    n: MockConnector(n) for n in ["slack", "documents", "meetings"]
}
# Future connectors: REGISTRY["github"] = GithubConnector() etc.