import traceback
from .models import Research, Status, Step, Finding
from .connectors import REGISTRY
from .rbac import get_user
from .planner import plan
from .analyzer import analyze, build_report
from . import store

STEP_NAMES = [
    "Understanding the question", "Breaking question into research areas",
    "Searching sources", "Collecting evidence", "Cross-referencing evidence",
    "Identifying patterns", "Generating report",
]


def _set(r: Research, idx: int, status: str, detail: str = ""):
    r.steps[idx].status = status
    r.steps[idx].detail = detail
    store.save(r)


def run(research_id: str):
    r = store.get(research_id)
    try:
        user = get_user(r.user_id)
        r.steps = [Step(name=n) for n in STEP_NAMES]

        r.status = Status.planning
        _set(r, 0, "done")
        _set(r, 1, "running", "Decomposing the question")
        r.areas, r.queries = plan(r.question)
        _set(r, 1, "done", f"{len(r.areas)} research areas")

        r.status = Status.searching
        seen = set()
        for area in r.areas:
            for q in r.queries.get(area, [area]):
                for src in r.sources:
                    _set(r, 2, "running", f"Searching {src} for: {q}")
                    conn = REGISTRY.get(src)
                    if not conn:
                        continue
                    for ev in conn.search(q, user):
                        if ev.url in seen:
                            continue
                        seen.add(ev.url)
                        ev.research_area = area
                        r.evidence.append(ev)
        _set(r, 2, "done")

        r.status = Status.collecting_evidence
        _set(r, 3, "done", f"{len(r.evidence)} evidence items collected")

        r.status = Status.analyzing
        _set(r, 4, "running", "Cross-referencing evidence across sources")
        analysis = analyze(r)
        r.findings = [Finding(**f) for f in analysis["findings"]]
        _set(r, 4, "done")
        _set(r, 5, "done", f"{len(analysis['patterns'])} patterns, {len(analysis['causes'])} potential causes")

        r.status = Status.generating_report
        _set(r, 6, "running", "Writing the report")
        r.report = build_report(r, analysis)
        _set(r, 6, "done")

        r.status = Status.completed
        store.save(r)
    except Exception:
        r.status = Status.failed
        r.error = traceback.format_exc()
        store.save(r)