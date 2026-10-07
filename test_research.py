import re
import time
from datetime import datetime

from app import store
from app.models import Research
from app.pipeline import run
from app.rbac import get_user

ALL = ["slack", "documents", "meetings"]

# (question, user, expects_evidence)
CASES = [
    ("Why did our Q3 sales pipeline slow down?", "admin", True),
    ("Why are enterprise customers reporting onboarding issues?", "admin", True),
    ("What are the biggest product risks this quarter?", "admin", True),
    ("Why is mid-market churn increasing?", "admin", True),
    ("How is sales team capacity affecting our Q3 results?", "admin", True),
    ("Why did our Q3 sales pipeline slow down?", "intern", True),   # RBAC case
    ("What is our office parking policy?", "admin", False),          # no-evidence case
]


def cited_ids(rep):
    ids = []
    for f in rep["key_findings"]:
        ids += f["evidence_ids"]
    for p in rep["patterns"]:
        ids += p["evidence_ids"]
    for c in rep["potential_causes"]:
        ids += c["evidence_ids"]
    for x in rep["recommendations"]:
        ids += x["based_on"]
    return ids


def check(r: Research, user_id: str, expects_evidence: bool):
    res = []
    rep = r.report or {}
    res.append(("pipeline completed", r.status.value == "completed"))
    if r.status.value != "completed":
        return res

    blocked = get_user(user_id).blocked_resources
    refs = {e.reference for e in r.evidence}
    res.append(("RBAC: no blocked resources in evidence", not (refs & blocked)))
    res.append(("planner made 4+ areas", len(r.areas) >= 4))

    if expects_evidence:
        types = {e.source_type for e in r.evidence}
        res.append(("evidence found", len(r.evidence) > 0))
        res.append(("searched 2+ sources", len(types) >= 2))
        res.append(("findings generated", len(rep["key_findings"]) > 0))
        valid = {s["id"] for s in rep["sources"]}
        res.append(("all citations resolve to real evidence", all(i in valid for i in cited_ids(rep))))
        res.append(("every finding has a citation", all(f["evidence_ids"] for f in rep["key_findings"])))
        by_id = {e.id: e for e in r.evidence}
        cross = any(
            len({by_id[i].source_type for i in c["evidence_ids"] if i in by_id}) >= 2
            for c in rep["potential_causes"] + rep["patterns"]
        )
        res.append(("cross-source pattern or cause", cross))
        res.append(("evidence vs inference labelled", all(f["kind"] in ("evidence", "inference") for f in rep["key_findings"])))
        res.append(("single-source causes capped at 0.5",
                    all(c["confidence"] <= 0.5 for c in rep["potential_causes"] if not c.get("cross_source"))))
        res.append(("summary has no raw ids", not re.search(r"\b[0-9a-f]{8}\b", rep["executive_summary"])))
    else:
        res.append(("no findings or causes invented", not rep["key_findings"] and not rep["potential_causes"]))
        res.append(("summary says no relevant evidence", "no accessible evidence" in rep["executive_summary"].lower()))
        res.append(("no irrelevant sources shown", len(rep["sources"]) == 0))
    return res


def main():
    lines = [f"# Test results ({datetime.now():%Y-%m-%d %H:%M})\n"]
    total = passed = 0
    for n, (q, user, exp) in enumerate(CASES, 1):
        r = Research(user_id=user, question=q, sources=ALL)
        store.save(r)
        run(r.id)
        r = store.get(r.id)
        results = check(r, user, exp)

        head = f"Case {n} [{user}]: {q}"
        print("\n" + head)
        lines.append(f"\n## {head}\n")
        for name, ok in results:
            total += 1
            passed += ok
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            lines.append(f"- {'PASS' if ok else 'FAIL'}: {name}")

        if r.report:
            print(f"  evidence: {len(r.evidence)} | areas: {len(r.areas)}")
            print(f"  summary: {r.report['executive_summary'][:220]}")
            lines.append(f"\nSummary: {r.report['executive_summary']}\n")
            for c in r.report["potential_causes"]:
                tag = "multi" if c.get("cross_source") else "single"
                print(f"  cause [{tag} {c['confidence']:.2f}]: {c['title']}")
                lines.append(f"- Cause ({tag}, {c['confidence']:.2f}): {c['title']}")
        if r.error:
            print("  error:", r.error.strip().splitlines()[-1])
        time.sleep(2)  # be gentle with rate limits

    summary = f"\nTOTAL: {passed}/{total} checks passed"
    print(summary)
    lines.append(f"\n**{summary.strip()}**")
    with open("test_results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Saved test_results.md")


if __name__ == "__main__":
    main()