from collections import Counter, defaultdict
from . import llm
from .models import Research

ANALYZE_SYSTEM = """You are a research analyst. You get evidence items, each with an id like [ab12cd34].
Use ONLY the given evidence. Never invent facts, numbers, names or dates.
Return ONLY JSON:
{
 "answerable": true,
 "findings": [{"kind": "evidence", "statement": "...", "evidence_ids": ["id"], "confidence": 0.0}],
 "patterns": [{"title": "...", "description": "...", "evidence_ids": ["id"]}],
 "causes": [{"title": "...", "explanation": "...", "evidence_ids": ["id"], "confidence": 0.0}]
}
Rules:
- kind "evidence" = directly stated in the evidence. kind "inference" = your hypothesis from combining evidence.
- A pattern or cause must combine evidence from at least 2 items, ideally from different sources.
- Every item must cite evidence_ids from the list. Do not state counts, only describe what is said.
- Confidence between 0 and 1. Lower it when evidence is thin or from a single source.
- If other evidence limits or contradicts a cause (for example it concerns a different customer segment), say so in the explanation and lower the confidence.
- For kind "inference" and for causes, use cautious wording such as "may" or "likely". Never state a cause as certain.
- 4 to 8 findings, 2 to 4 patterns, 2 to 4 causes.
- Cite only evidence that directly supports the cause. Do not cite evidence about a different topic just to add sources.
- Mention in the explanation any evidence that argues against the cause.
- Set "answerable" to false if the evidence does not actually relate to the question, and return empty lists. Never stretch unrelated evidence to fit the question."""

REPORT_SYSTEM = """You write the summary part of a research report.
Use ONLY the findings, patterns and causes given. Do not add new facts.
Use "the evidence suggests" for causes. Say which causes are backed by several sources and which by a single source. Do not use "because" as a certain claim.
Do not generalize beyond what the evidence says (for example, do not widen a segment or add effects like win rates unless stated). Do not write evidence ids inside the summary text.
Return ONLY JSON:
{"executive_summary": "3 to 4 sentences, direct answer to the question, say clearly what is inference",
 "recommendations": [{"text": "...", "based_on": ["evidence ids"]}]}
Give 3 to 5 recommendations, each tied to evidence ids from the input."""


def group_by_area(r: Research) -> dict:
    g = defaultdict(list)
    for e in r.evidence:
        g[e.research_area].append(e.id)
    return dict(g)


def _clean(ids, valid):
    return [i for i in ids if i in valid]


def _evidence_block(r: Research) -> str:
    items = sorted(r.evidence, key=lambda e: e.score, reverse=True)[:40]
    return "\n".join(
        f"[{e.id}] ({e.source_type}/{e.reference}, {e.date}, area: {e.research_area}) {e.snippet[:300]}"
        for e in items
    )


def _fallback_analysis(r: Research) -> dict:
    out = {"findings": [], "patterns": [], "causes": []}
    for area, ids in group_by_area(r).items():
        out["findings"].append({"kind": "evidence",
            "statement": f"{len(ids)} item(s) found related to: {area}",
            "evidence_ids": ids, "confidence": 0.5})
    return out


def analyze(r: Research) -> dict:
    valid = {e.id for e in r.evidence}
    by_id = {e.id: e for e in r.evidence}
    if not r.evidence:
        return {"findings": [], "patterns": [], "causes": []}

    if not llm.available():
        return _fallback_analysis(r)

    try:
        data = llm.ask_json(ANALYZE_SYSTEM,
            f"Question: {r.question}\n\nEvidence:\n{_evidence_block(r)}", max_tokens=2500)
    except Exception as e:
        print("Analysis LLM failed, using fallback:", e)
        return _fallback_analysis(r)

    if data.get("answerable") is False:
        return {"findings": [], "patterns": [], "causes": [], "answerable": False}

    result = {"findings": [], "patterns": [], "causes": []}
    for f in data.get("findings", []):
        ids = _clean(f.get("evidence_ids", []), valid)
        if not ids or not f.get("statement"):
            continue  # unsupported claim, drop it
        kind = f.get("kind") if f.get("kind") in ("evidence", "inference") else "inference"
        result["findings"].append({"kind": kind, "statement": f["statement"],
            "evidence_ids": ids, "confidence": float(f.get("confidence", 0.5))})
    for p in data.get("patterns", []):
        ids = _clean(p.get("evidence_ids", []), valid)
        if len(ids) >= 2:
            result["patterns"].append({"title": p.get("title", ""),
                "description": p.get("description", ""), "evidence_ids": ids})
    for c in data.get("causes", []):
        ids = _clean(c.get("evidence_ids", []), valid)
        if not ids:
            continue
        src_types = {by_id[i].source_type for i in ids}
        conf = float(c.get("confidence", 0.5))
        cross = len(ids) >= 2 and len(src_types) >= 2
        if not cross:
            conf = min(conf, 0.5)   # single-source cause cannot be high confidence
        result["causes"].append({"title": c.get("title", ""),
            "explanation": c.get("explanation", ""), "evidence_ids": ids,
            "confidence": conf, "cross_source": cross})
    return result


def build_report(r: Research, analysis: dict) -> dict:
    if analysis.get("answerable") is False:
        return {
            "executive_summary": "No accessible evidence relevant to this question was found in the selected sources.",
            "key_findings": [], "patterns": [], "potential_causes": [],
            "examples": [], "relevant_conversations": [], "recommendations": [],
            "sources": [],
            "stats": {"evidence_by_source": {}, "evidence_by_area": {}, "total_evidence": 0},
        }
    valid = {e.id for e in r.evidence}
    by_id = {e.id: e for e in r.evidence}
    src_counts = dict(Counter(e.source_type for e in r.evidence))
    area_counts = {a: len(ids) for a, ids in group_by_area(r).items()}

    summary, recs = "", []
    if not r.evidence:
        summary = "No accessible evidence was found for this question in the selected sources."
    elif llm.available():
        try:
            data = llm.ask_json(REPORT_SYSTEM,
                f"Question: {r.question}\n\nAnalysis:\n{analysis}", max_tokens=1200)
            summary = data.get("executive_summary", "")
            for rec in data.get("recommendations", []):
                ids = _clean(rec.get("based_on", []), valid)
                if ids and rec.get("text"):
                    recs.append({"text": rec["text"], "based_on": ids})
        except Exception as e:
            print("Report LLM failed:", e)
    if not summary and r.evidence:
        summary = f"Found {len(r.evidence)} evidence items across {len(src_counts)} source(s). See findings below."

    cited = []
    for c in analysis["causes"]:
        cited += c["evidence_ids"]
    examples = [by_id[i] for i in dict.fromkeys(cited)][:5]

    return {
        "executive_summary": summary,
        "key_findings": analysis["findings"],
        "patterns": analysis["patterns"],
        "potential_causes": analysis["causes"],
        "examples": [e.model_dump() for e in examples],
        "relevant_conversations": [e.model_dump() for e in sorted(r.evidence, key=lambda e: e.date, reverse=True)],
        "recommendations": recs,
        "sources": [e.model_dump() for e in r.evidence],
        "stats": {"evidence_by_source": src_counts, "evidence_by_area": area_counts,
                  "total_evidence": len(r.evidence)},
    }