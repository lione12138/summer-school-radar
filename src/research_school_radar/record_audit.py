from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .ai_cache import AICache
from .atomic_io import write_text_atomic
from .llm_client import BaseLLMClient, LLMUnavailableError
from .models import Candidate, Page
from .rank import canonical_url
from .utils import clean_space, content_hash, load_yaml


AUDIT_SCHEMA_VERSION = "record-audit-v1"
PROMPT_VERSION = "record-audit-prompt-v1"

_ALLOWED_FIELDS = {
    "title",
    "organizer",
    "location",
    "mode",
    "start_date",
    "end_date",
    "sessions",
    "deadline",
    "deadline_status",
    "fee",
    "funding",
    "eligibility",
    "summary",
    "topics",
    "application_link",
}
_ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
_ALLOWED_VERDICTS = {"pass", "needs_correction", "reject"}
_NAVIGATION_RE = re.compile(
    r"\b(?:skip to content|accessibility help|cookie(?:s)?|menu home|go to content|"
    r"doctoral guide|alumni|contact us|privacy policy)\b",
    flags=re.IGNORECASE,
)
_LOCATION_CONTAMINATION_RE = re.compile(
    r"\b(?:open to|who (?:can|should) apply|eligibility|application|registration|hosts?)\b",
    flags=re.IGNORECASE,
)
_RELEVANT_RE = re.compile(
    r"\b(?:organis(?:e|ed|er|ing)|organiz(?:e|ed|er|ing)|host(?:ed|ing)?|run by|"
    r"venue|location|held at|take place|deadline|apply|application|registration|"
    r"fee|tuition|cost|free|fund(?:ed|ing)?|grant|scholarship|bursary|stipend|"
    r"travel|accommodation|access fund|eligible|eligibility|open to|who can apply|"
    r"master'?s|phd|postdoc|doctoral|start date|end date|programme dates?|session)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RecordAuditConfig:
    enabled: bool = True
    max_records: int = 80
    max_workers: int = 4
    max_attempts: int = 2
    max_evidence_snippets: int = 9
    max_chars_per_snippet: int = 1000
    max_total_evidence_chars: int = 7000
    max_tokens: int = 1800


def load_record_audit_config(path: Path) -> RecordAuditConfig:
    raw: dict[str, Any] = {}
    if path.exists():
        value = load_yaml(path).get("record_audit", {})
        if isinstance(value, dict):
            raw = value
    return RecordAuditConfig(
        enabled=bool(raw.get("enabled", True)),
        max_records=max(0, int(raw.get("max_records", 80))),
        max_workers=max(1, int(raw.get("max_workers", 4))),
        max_attempts=max(1, int(raw.get("max_attempts", 2))),
        max_evidence_snippets=max(1, int(raw.get("max_evidence_snippets", 9))),
        max_chars_per_snippet=max(200, int(raw.get("max_chars_per_snippet", 1000))),
        max_total_evidence_chars=max(1000, int(raw.get("max_total_evidence_chars", 7000))),
        max_tokens=max(500, int(raw.get("max_tokens", 1800))),
    )


def audit_key(candidate: Candidate) -> str:
    if candidate.identity_key.strip():
        return candidate.identity_key.strip()
    payload = {
        "source_url": canonical_url(candidate.source_url),
        "application_link": canonical_url(candidate.application_link),
        "title": clean_space(candidate.title).casefold(),
    }
    return "record:" + content_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def record_context(candidate: Candidate) -> dict[str, Any]:
    return {
        "title": candidate.title,
        "organizer": candidate.organizer,
        "location": candidate.location,
        "mode": candidate.mode,
        "start_date": _iso(candidate.start_date),
        "end_date": _iso(candidate.end_date),
        "duration_days": candidate.duration_days,
        "sessions": [
            {
                "name": session.name,
                "start_date": session.start_date.isoformat(),
                "end_date": session.end_date.isoformat(),
                "application_deadline": _iso(session.application_deadline),
            }
            for session in candidate.sessions
        ],
        "deadline": _iso(candidate.deadline),
        "deadline_status": candidate.deadline_status,
        "fee": candidate.fee,
        "fee_eur": candidate.fee_eur,
        "funding_available": candidate.funding_available,
        "funding_type": candidate.funding_type,
        "funding_scope": candidate.funding_scope,
        "funding_evidence": candidate.funding_evidence,
        "eligibility": candidate.eligibility,
        "summary": candidate.summary,
        "topics": candidate.topic_keywords,
        "application_link": candidate.application_link,
        "source_url": candidate.source_url,
    }


def build_evidence_packet(
    candidate: Candidate,
    pages: Sequence[Page],
    ai_items: Sequence[dict[str, Any]] | None,
    config: RecordAuditConfig,
) -> list[dict[str, str]]:
    snippets: list[tuple[str, str, str]] = []
    for label, value in (
        ("deadline_evidence", candidate.deadline_evidence),
        ("duration_evidence", candidate.duration_evidence),
        ("funding_evidence", candidate.funding_evidence),
        ("mode_evidence", candidate.mode_evidence),
        ("eligibility_extract", candidate.eligibility),
        ("summary_extract", candidate.summary),
    ):
        if clean_space(value):
            snippets.append((label, candidate.source_url, clean_space(value)))

    candidate_urls = {
        canonical_url(url)
        for url in (candidate.source_url, candidate.application_link)
        if canonical_url(url)
    }
    for page in pages:
        if canonical_url(page.url) not in candidate_urls:
            continue
        for text in _relevant_page_windows(page.text, candidate.title, config):
            snippets.append(("official_page", page.url, text))

    for item in ai_items or []:
        if canonical_url(str(item.get("page_url", ""))) not in candidate_urls:
            continue
        extraction = item.get("llm_extraction")
        if not isinstance(extraction, dict):
            continue
        for field, value in extraction.items():
            if not isinstance(value, dict):
                continue
            texts = value.get("resolved_evidence_texts")
            if not isinstance(texts, list):
                continue
            for text in texts:
                cleaned = clean_space(str(text))
                if cleaned:
                    snippets.append((f"ai_evidence:{field}", str(item.get("page_url", "")), cleaned))

    deduplicated: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    total = 0
    for kind, source_url, text in snippets:
        clipped = text[: config.max_chars_per_snippet].strip()
        fingerprint = content_hash(clipped.casefold())
        if not clipped or fingerprint in seen:
            continue
        if total + len(clipped) > config.max_total_evidence_chars:
            remaining = config.max_total_evidence_chars - total
            if remaining < 200:
                break
            clipped = clipped[:remaining].rstrip()
        seen.add(fingerprint)
        deduplicated.append((kind, source_url, clipped))
        total += len(clipped)
        if len(deduplicated) >= config.max_evidence_snippets:
            break
    return [
        {"id": f"E{index}", "kind": kind, "source_url": source_url, "text": text}
        for index, (kind, source_url, text) in enumerate(deduplicated, start=1)
    ]


def deterministic_record_issues(candidate: Candidate, *, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    issues: list[dict[str, Any]] = []
    if candidate.start_date and candidate.end_date and candidate.end_date < candidate.start_date:
        issues.append(_rule_issue("end_date", "critical", "Programme end date precedes its start date."))
    if candidate.deadline and candidate.status_reference_start and candidate.deadline > candidate.status_reference_start:
        issues.append(_rule_issue("deadline", "high", "Application deadline is after the programme starts."))
    if candidate.deadline and candidate.deadline < today and candidate.deadline_status == "open":
        issues.append(_rule_issue("deadline_status", "high", "A past application deadline is marked open."))
    if candidate.start_date and candidate.start_date <= today and candidate.deadline_status == "open":
        issues.append(_rule_issue("deadline_status", "high", "A programme that has started is marked open."))
    if (
        candidate.start_date
        and candidate.end_date
        and not candidate.sessions
        and candidate.duration_days is not None
        and candidate.duration_days != (candidate.end_date - candidate.start_date).days + 1
    ):
        issues.append(_rule_issue("end_date", "medium", "Displayed duration conflicts with the date range."))
    if _LOCATION_CONTAMINATION_RE.search(candidate.location):
        issues.append(_rule_issue("location", "high", "Location contains an adjacent webpage field label."))
    navigation_hits = len(_NAVIGATION_RE.findall(candidate.summary))
    if navigation_hits >= 2:
        issues.append(_rule_issue("summary", "high", "Summary contains repeated navigation or cookie text."))
    elif navigation_hits == 1:
        issues.append(_rule_issue("summary", "medium", "Summary may contain navigation or cookie text."))
    if candidate.funding_available is False and (candidate.funding_type or candidate.funding_scope.strip()):
        issues.append(_rule_issue("funding", "high", "Funding is marked unavailable but funding benefits are populated."))
    return issues


def run_record_audit(
    candidates: Sequence[Candidate],
    pages: Sequence[Page],
    *,
    client: BaseLLMClient,
    config: RecordAuditConfig,
    cache: AICache | None = None,
    ai_items: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    selected = list(candidates[: config.max_records])
    if not selected:
        return []

    def audit_one(candidate: Candidate) -> dict[str, Any]:
        evidence = build_evidence_packet(candidate, pages, ai_items, config)
        context = record_context(candidate)
        deterministic = deterministic_record_issues(candidate)
        key = _cache_key(candidate, context, evidence, client, config)
        cached = cache.get("record_audit", key) if cache is not None else None
        if isinstance(cached, dict):
            validated = _validated_model_result(cached, candidate, evidence)
            return _audit_item(candidate, evidence, deterministic, validated, cache_hit=True)

        if not evidence:
            return _audit_item(
                candidate,
                evidence,
                deterministic,
                {"verdict": "pass", "issues": [], "warnings": ["record_audit_no_source_evidence"]},
                cache_hit=False,
            )

        prompt = _audit_prompt(context, evidence)
        last_warning = "record_audit_invalid_json"
        for _attempt in range(config.max_attempts):
            try:
                raw = client.complete(prompt)
            except LLMUnavailableError as exc:
                last_warning = f"record_audit_unavailable:{exc}"
                break
            parsed = _parse_json_object(raw)
            if parsed is None:
                continue
            validated = _validated_model_result(parsed, candidate, evidence)
            if cache is not None:
                cache.set("record_audit", key, parsed)
            return _audit_item(candidate, evidence, deterministic, validated, cache_hit=False)
        return _audit_item(
            candidate,
            evidence,
            deterministic,
            {"verdict": "pass", "issues": [], "warnings": [last_warning]},
            cache_hit=False,
        )

    workers = min(config.max_workers, len(selected))
    if workers <= 1:
        return [audit_one(candidate) for candidate in selected]
    completed: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(audit_one, candidate): index for index, candidate in enumerate(selected)}
        for future in as_completed(futures):
            completed[futures[future]] = future.result()
    return [completed[index] for index in range(len(selected))]


def filter_display_candidates_by_audit(
    candidates: Sequence[Candidate],
    audit_items: Sequence[dict[str, Any]] | None,
) -> list[Candidate]:
    rejected = {
        str(item.get("audit_key", ""))
        for item in audit_items or []
        if item.get("gate_publication") is True
    }
    if not rejected:
        return list(candidates)
    return [candidate for candidate in candidates if audit_key(candidate) not in rejected]


def write_record_audit_sidecars(
    items: Sequence[dict[str, Any]],
    *,
    site_dir: Path,
    reports_dir: Path,
    provider: str,
    model: str,
    requested_records: int,
    cache: AICache | None = None,
) -> tuple[Path, Path, Path]:
    operational_warnings = sorted(
        {
            warning
            for item in items
            for warning in item.get("validation_warnings", [])
            if str(warning).startswith(
                ("record_audit_unavailable:", "record_audit_invalid_json", "record_audit_no_source_evidence")
            )
        }
    )
    payload = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "provider": provider,
        "model": model,
        "requested_records": requested_records,
        "audited_records": len(items),
        "rejected_records": sum(item.get("gate_publication") is True for item in items),
        "cache_hits": sum(item.get("cache_hit") is True for item in items),
        "warnings": [*operational_warnings, *(cache.warnings if cache is not None else [])],
        "items": list(items),
    }
    site_path = site_dir / "record-audit.json"
    report_json = reports_dir / f"{date.today().isoformat()}.record-audit.json"
    report_markdown = reports_dir / f"{date.today().isoformat()}.record-audit.md"
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    write_text_atomic(site_path, serialized)
    write_text_atomic(report_json, serialized)
    write_text_atomic(report_markdown, _markdown_report(payload))
    return site_path, report_json, report_markdown


def _audit_item(
    candidate: Candidate,
    evidence: list[dict[str, str]],
    deterministic: list[dict[str, Any]],
    model_result: dict[str, Any],
    *,
    cache_hit: bool,
) -> dict[str, Any]:
    model_issues = list(model_result.get("issues", []))
    issues = [*deterministic, *model_issues]
    model_verdict = str(model_result.get("verdict", "pass"))
    deterministic_gate = any(
        issue.get("severity") in {"high", "critical"} for issue in deterministic
    )
    evidence_backed_reject = model_verdict == "reject" and any(
        issue.get("severity") in {"high", "critical"} and issue.get("evidence_ids")
        for issue in model_issues
    )
    verdict = "reject" if deterministic_gate or evidence_backed_reject else (
        "needs_correction" if issues else "pass"
    )
    warnings = [str(value) for value in model_result.get("warnings", [])]
    return {
        "audit_key": audit_key(candidate),
        "identity_key": candidate.identity_key,
        "title": candidate.title,
        "source_url": candidate.source_url,
        "verdict": verdict,
        "gate_publication": verdict == "reject",
        "issues": issues,
        "evidence": evidence,
        "validation_warnings": warnings,
        "cache_hit": cache_hit,
    }


def _validated_model_result(
    payload: dict[str, Any],
    candidate: Candidate,
    evidence: Sequence[dict[str, str]],
) -> dict[str, Any]:
    warnings: list[str] = []
    verdict = clean_space(str(payload.get("verdict", "pass"))).lower()
    if verdict not in _ALLOWED_VERDICTS:
        warnings.append("record_audit_invalid_verdict")
        verdict = "pass"
    evidence_ids = {item["id"] for item in evidence}
    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        warnings.append("record_audit_invalid_issues")
        raw_issues = []
    issues: list[dict[str, Any]] = []
    for raw in raw_issues[:12]:
        if not isinstance(raw, dict):
            warnings.append("record_audit_invalid_issue")
            continue
        field = clean_space(str(raw.get("field", ""))).lower()
        severity = clean_space(str(raw.get("severity", ""))).lower()
        cited = raw.get("evidence_ids", [])
        cited_ids = [clean_space(str(value)) for value in cited] if isinstance(cited, list) else []
        if field not in _ALLOWED_FIELDS or severity not in _ALLOWED_SEVERITIES:
            warnings.append("record_audit_invalid_issue_contract")
            continue
        if not cited_ids or any(value not in evidence_ids for value in cited_ids):
            warnings.append(f"record_audit_invalid_evidence:{field}")
            continue
        reason = clean_space(str(raw.get("reason", "")))[:600]
        suggested = clean_space(str(raw.get("suggested_value", "")))[:600]
        if not reason:
            warnings.append(f"record_audit_missing_reason:{field}")
            continue
        issues.append(
            {
                "field": field,
                "severity": severity,
                "current_value": _current_field_value(candidate, field),
                "suggested_value": suggested,
                "evidence_ids": list(dict.fromkeys(cited_ids)),
                "reason": reason,
                "origin": "deepseek",
            }
        )
    if verdict == "reject" and not any(
        issue["severity"] in {"high", "critical"} for issue in issues
    ):
        warnings.append("record_audit_reject_without_high_issue")
        verdict = "needs_correction" if issues else "pass"
    return {"verdict": verdict, "issues": issues, "warnings": warnings}


def _current_field_value(candidate: Candidate, field: str) -> Any:
    values = record_context(candidate)
    if field == "funding":
        return {
            "available": candidate.funding_available,
            "type": candidate.funding_type,
            "scope": candidate.funding_scope,
        }
    if field == "topics":
        return candidate.topic_keywords
    return values.get(field, "")


def _rule_issue(field: str, severity: str, reason: str) -> dict[str, Any]:
    return {
        "field": field,
        "severity": severity,
        "current_value": "",
        "suggested_value": "",
        "evidence_ids": [],
        "reason": reason,
        "origin": "deterministic",
    }


def _relevant_page_windows(text: str, title: str, config: RecordAuditConfig) -> list[str]:
    cleaned = clean_space(text)
    if not cleaned:
        return []
    matches = list(_RELEVANT_RE.finditer(cleaned))
    title_terms = [term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", title)[:8]]
    windows: list[tuple[int, str]] = []
    for match in matches[:80]:
        start = max(0, match.start() - 260)
        end = min(len(cleaned), match.end() + 620)
        snippet = cleaned[start:end].strip()
        score = len(_RELEVANT_RE.findall(snippet)) * 3
        score += sum(term in snippet.casefold() for term in title_terms)
        windows.append((score, snippet))
    if not windows:
        windows.append((0, cleaned[: config.max_chars_per_snippet]))
    selected: list[str] = []
    seen: set[str] = set()
    for _score, snippet in sorted(windows, key=lambda item: item[0], reverse=True):
        fingerprint = content_hash(snippet[:400].casefold())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append(snippet[: config.max_chars_per_snippet])
        if len(selected) >= config.max_evidence_snippets:
            break
    return selected


def _audit_prompt(context: dict[str, Any], evidence: Sequence[dict[str, str]]) -> str:
    return (
        "You are the final evidence auditor for Summa, an academic research-training directory.\n"
        "Audit the complete record for factual consistency and source fidelity. The record is a claim, not evidence.\n"
        "Check organizer role (organizer vs publisher/network/member category), venue/location contamination, "
        "dates and application status, fee versus funding semantics, eligibility, summary navigation noise, topics, "
        "and multi-session interpretation.\n"
        "Use only the supplied evidence snippets. Never infer a correction from general knowledge. "
        "Every issue must cite one or more supplied evidence IDs. If evidence is insufficient, do not invent an issue.\n"
        "Use verdict=reject only when a high/critical, evidence-backed error makes public display misleading or unsafe. "
        "Use needs_correction for supported non-blocking inaccuracies, otherwise pass.\n"
        "Return one JSON object only with this schema:\n"
        '{"verdict":"pass|needs_correction|reject","issues":['
        '{"field":"allowed field","severity":"low|medium|high|critical",'
        '"current_value":"...","suggested_value":"...","evidence_ids":["E1"],"reason":"..."}]}\n'
        f"Allowed fields: {', '.join(sorted(_ALLOWED_FIELDS))}.\n"
        f"RECORD:\n{json.dumps(context, ensure_ascii=False, default=str)}\n"
        f"EVIDENCE:\n{json.dumps(list(evidence), ensure_ascii=False)}"
    )


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _cache_key(
    candidate: Candidate,
    context: dict[str, Any],
    evidence: Sequence[dict[str, str]],
    client: BaseLLMClient,
    config: RecordAuditConfig,
) -> str:
    payload = {
        "audit_key": audit_key(candidate),
        "record": context,
        "evidence": [{"kind": item["kind"], "text": item["text"]} for item in evidence],
        "model": client.config.model,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "max_tokens": config.max_tokens,
    }
    return content_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str))


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Summa Record Audit",
        "",
        f"Generated: {payload['generated']}",
        "",
        f"Audited: {payload['audited_records']} / {payload['requested_records']}",
        f"Publication gates: {payload['rejected_records']}",
        "",
    ]
    for item in payload.get("items", []):
        lines.extend([f"## {item.get('title', 'Untitled')}", "", f"Verdict: **{item.get('verdict')}**", ""])
        for issue in item.get("issues", []):
            evidence_ids = ", ".join(issue.get("evidence_ids", [])) or "deterministic"
            lines.append(
                f"- `{issue.get('field')}` · {issue.get('severity')} · {issue.get('reason')} ({evidence_ids})"
            )
        if not item.get("issues"):
            lines.append("- No supported issue found.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
