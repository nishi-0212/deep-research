from . import llm

SYSTEM = """You are a research planner for a company knowledge assistant.
Given a business question, break it into 5 to 8 distinct research areas.
For each area, give 2 to 4 short keyword-style search queries (3 to 6 words each)
that would find relevant messages, documents or meeting notes.
Cover internal factors (team, process, product), customer-side factors (objections, pricing, delays) and external factors (competitors, market).
Do not assume facts. Only plan what to look for.
Return ONLY JSON in this shape:
{"areas": [{"area": "Customer objections", "queries": ["customer objection", "deal blocked"]}]}"""


def _fallback(question: str):
    areas = [question, "customer objections", "pricing discussions",
             "onboarding implementation delays", "competitor mentions"]
    return areas, {a: [a] for a in areas}


def plan(question: str):
    """Returns (areas, queries_by_area)."""
    if not llm.available():
        return _fallback(question)
    try:
        data = llm.ask_json(SYSTEM, f"Question: {question}")
        areas, queries = [], {}
        for item in data["areas"]:
            name = item["area"].strip()
            qs = [q.strip() for q in item.get("queries", []) if q.strip()]
            if name and qs:
                areas.append(name)
                queries[name] = qs
        if not areas:
            return _fallback(question)
        return areas, queries
    except Exception as e:
        print("Planner failed, using fallback:", e)
        return _fallback(question)