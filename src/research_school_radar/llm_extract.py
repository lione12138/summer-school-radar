from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .ai_cache import AICache, llm_cache_key
from .evidence_snippets import build_evidence_snippets
from .llm_client import BaseLLMClient, LLMClientConfig
from .llm_validate import validate_llm_extraction
from .models import Candidate
from .semantic import SemanticChunk, semantic_page_matches_candidate
from .utils import clean_space, write_text_atomic


AI_EXTRACTION_SCHEMA_VERSION = "v7-follow-up-evidence"

_SCHEMA = {
    "page_type": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "title": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "event_type": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "location": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "mode": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "start_date": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "end_date": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "application_deadline": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "application_deadline_type": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "other_deadlines": {"value": [], "evidence_ids": [], "resolved_evidence_texts": []},
    "registration_status": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "fee": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "funding": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "eligibility": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "application_url": {"value": "unknown", "evidence_ids": [], "resolved_evidence_texts": []},
    "topics": {"value": [], "evidence_ids": [], "resolved_evidence_texts": []},
    "chinese_summary": {"value": "", "evidence_ids": [], "resolved_evidence_texts": []},
    "confidence": "low",
    "warnings": [],
}


def parse_llm_json(response: str) -> dict[str, Any] | None:
    stripped = _strip_code_fence(response)
    cleaned = _remove_thinking_sections(stripped)
    candidates = [
        response,
        stripped,
        cleaned,
        _first_json_object(cleaned),
        _first_json_object(response),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return parsed if isinstance(parsed, dict) else None
    return None


def run_llm_extraction(
    chunks: Sequence[SemanticChunk],
    *,
    candidates: Sequence[Candidate],
    client: BaseLLMClient,
    max_pages_for_llm: int,
    max_chunks_per_page: int,
    max_chars_per_chunk: int = 4000,
    max_total_chars_per_llm_request: int = 12000,
    cache: AICache | None = None,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page_chunks in _chunks_by_page(chunks, max_pages=max_pages_for_llm, max_chunks=max_chunks_per_page):
        page_chunks, limit_warnings = _limit_chunks(
            page_chunks,
            max_chars_per_chunk=max_chars_per_chunk,
            max_total_chars=max_total_chars_per_llm_request,
        )
        first = page_chunks[0]
        existing = _matching_candidate(first.page_url, candidates)
        cache_key = llm_cache_key(
            page_url=first.page_url,
            chunks=page_chunks,
            model=model_name or getattr(getattr(client, "config", None), "model", ""),
            schema_version=AI_EXTRACTION_SCHEMA_VERSION,
        )
        cached = cache.get("llm", cache_key) if cache is not None else None
        if isinstance(cached, dict):
            item = dict(cached)
            cached_extraction = item.get("llm_extraction", {})
            cached_snippets = item.get("evidence_snippets", [])
            validation_warnings, confidence = validate_llm_extraction(
                cached_extraction if isinstance(cached_extraction, dict) else {},
                page_chunks,
                evidence_snippets=cached_snippets if isinstance(cached_snippets, list) else None,
            )
            item["validation_warnings"] = _dedupe(
                [
                    *limit_warnings,
                    *_cached_operational_warnings(item),
                    *validation_warnings,
                    *_llm_warnings(cached_extraction if isinstance(cached_extraction, dict) else {}),
                ]
            )
            item["validated_confidence"] = confidence
            items.append(item)
            continue

        evidence_snippets = build_evidence_snippets(list(page_chunks), max_snippets=20, max_chars=450)
        if not evidence_snippets:
            extraction = _with_schema_defaults({})
            validation_warnings, confidence = validate_llm_extraction(extraction, page_chunks, evidence_snippets=evidence_snippets)
            item = {
                "page_url": first.page_url,
                "page_title": first.page_title,
                "source_name": first.source_name,
                "semantic_score_max": round(max(chunk.score for chunk in page_chunks), 6),
                "matched_existing_candidate": semantic_page_matches_candidate(first.page_url, candidates),
                "existing_candidate_title": existing.title if existing else "",
                "evidence_snippets": [],
                "llm_extraction": extraction,
                "validation_warnings": _dedupe([*limit_warnings, "no_evidence_snippets", *validation_warnings]),
                "validated_confidence": "low",
            }
            if cache is not None:
                cache.set("llm", cache_key, item)
            items.append(item)
            continue

        prompt = build_llm_prompt(page_chunks, existing, evidence_snippets=evidence_snippets)
        warnings: list[str] = [*limit_warnings]
        extraction: dict[str, Any] = {}
        try:
            raw_response = client.complete(prompt)
        except Exception as exc:  # noqa: BLE001 - advisory extraction must not abort scan.
            warnings.append(f"llm_unavailable:{exc}")
            raw_response = ""
        warnings.extend(str(warning) for warning in getattr(client, "warnings", []))
        if raw_response:
            parsed = parse_llm_json(raw_response)
            if parsed is None:
                warnings.append("llm_json_parse_failed")
            else:
                extraction = _with_schema_defaults(parsed)
        extraction = resolve_evidence_texts(extraction, evidence_snippets)
        validation_warnings, confidence = validate_llm_extraction(
            extraction, page_chunks, evidence_snippets=evidence_snippets
        )
        item = {
            "page_url": first.page_url,
            "page_title": first.page_title,
            "source_name": first.source_name,
            "semantic_score_max": round(max(chunk.score for chunk in page_chunks), 6),
            "matched_existing_candidate": semantic_page_matches_candidate(first.page_url, candidates),
            "existing_candidate_title": existing.title if existing else "",
            "evidence_snippets": _public_evidence_snippets(evidence_snippets),
            "llm_extraction": extraction,
            "validation_warnings": _dedupe([*warnings, *validation_warnings, *_llm_warnings(extraction)]),
            "validated_confidence": confidence,
        }
        if cache is not None:
            cache.set("llm", cache_key, item)
        items.append(item)
    return items


def write_llm_sidecars(
    items: Sequence[dict[str, Any]],
    *,
    site_dir: Path,
    reports_dir: Path,
    config: LLMClientConfig,
    metadata: dict[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
) -> tuple[Path, Path]:
    payload = {
        "generated": date.today().isoformat(),
        "schema_version": AI_EXTRACTION_SCHEMA_VERSION,
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "fallback_model": config.fallback_model,
        "metadata": metadata or {},
        "warnings": list(warnings or []),
        "items": list(items),
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    site_path = site_dir / "ai_extractions.json"
    report_path = reports_dir / f"{date.today().isoformat()}.ai.json"
    write_text_atomic(site_path, text)
    write_text_atomic(report_path, text)
    return site_path, report_path


def build_llm_prompt(
    chunks: Sequence[SemanticChunk],
    existing: Candidate | None = None,
    evidence_snippets: Sequence[dict[str, Any]] | None = None,
) -> str:
    first = chunks[0]
    evidence_snippets = list(evidence_snippets) if evidence_snippets is not None else build_evidence_snippets(
        list(chunks), max_snippets=20, max_chars=450
    )
    return build_llm_prompt_from_snippets(first, evidence_snippets, existing)


def build_llm_prompt_from_snippets(
    first: SemanticChunk,
    evidence_snippets: Sequence[dict[str, Any]],
    existing: Candidate | None = None,
) -> str:
    existing_summary = ""
    if existing is not None:
        summary = {
            "title": existing.title,
            "deadline": existing.deadline.isoformat() if existing.deadline else "unknown",
            "fee": existing.fee or "unknown",
            "location": existing.location or "unknown",
            "source_url": existing.source_url,
            "application_link": existing.application_link,
        }
        existing_summary = f"\nExisting rule-based candidate summary:\n{json.dumps(summary, ensure_ascii=False)}\n"
    evidence_text = "\n".join(
        f"{snippet['id']}: [source: {snippet.get('page_url', first.page_url)}] "
        f"{clean_space(str(snippet['text']))} [signals: {', '.join(snippet.get('signals', []))}]"
        for snippet in evidence_snippets
    )
    return (
        "You are an evidence-grounded information extraction system.\n"
        "You are given numbered evidence snippets from one or more official webpages for a possible opportunity.\n"
        "Extract only facts directly supported by the numbered evidence snippets.\n"
        "Do not use outside knowledge. Do not infer missing dates, deadlines, fees, locations, eligibility, URLs, or funding.\n"
        "For each non-unknown field, cite one or more evidence_ids from the provided snippets.\n"
        "Only use evidence_ids that appear in the input. If no evidence ID supports a field, return value=\"unknown\" and evidence_ids=[].\n"
        "Do not output evidence_text. Do not output thinking, reasoning, or chain-of-thought. Return JSON only.\n"
        "First classify page_type as opportunity|application|fees|funding|index|other|unknown.\n"
        "For index/listing pages, do not synthesize event date ranges or locations; add warning index_or_listing_page.\n"
        "Evidence from multiple pages may be combined only when the title and edition year clearly identify the same opportunity. "
        "If pages conflict or refer to different editions, return unknown for the conflicting field and add warning conflicting_evidence.\n"
        "Set registration_status to open|not_yet_open|closed|unknown. Explicit wording such as 'registration is closed' "
        "overrides an apparently future date.\n"
        "application_deadline must be the deadline to apply or register for the opportunity. Do not use payment, invoice, "
        "abstract, accommodation, scholarship, or travel-grant deadlines as application_deadline. Put those in other_deadlines.\n"
        "Set application_deadline_type to application|registration|early_bird|regular_registration|late_registration|unknown. "
        "When several registration deadlines exist, use the latest generally available registration deadline, not only early bird.\n"
        "Preserve all relevant participant fee tiers and currencies. Never report only the cheapest fee when the evidence lists multiple tiers.\n"
        "Normalize unambiguous dates to YYYY-MM-DD. Keep unknown when the year is absent and cannot be resolved from the same edition evidence.\n\n"
        f"Current date: {date.today().isoformat()}\n"
        f"Page title: {first.page_title}\n"
        f"Page URL: {first.page_url}\n"
        f"Source name: {first.source_name}\n"
        f"{existing_summary}\n"
        "Schema: object fields page_type,title,event_type,location,mode,start_date,end_date,application_deadline,"
        "application_deadline_type,other_deadlines,registration_status,fee,funding,eligibility,application_url,topics,"
        "chinese_summary use {\"value\":...,\"evidence_ids\":[]}.\n"
        "event_type must be summer school|winter school|training school|field school|short course|doctoral school|unknown.\n"
        "mode must be in-person|hybrid|online|unknown. confidence must be high|medium|low. warnings is a string array.\n\n"
        "Evidence snippets:\n"
        f"{evidence_text}"
    )


def _limit_chunks(
    chunks: Sequence[SemanticChunk],
    *,
    max_chars_per_chunk: int,
    max_total_chars: int,
) -> tuple[list[SemanticChunk], list[str]]:
    warnings: list[str] = []
    limited: list[SemanticChunk] = []
    remaining = max(0, max_total_chars)
    per_chunk_limit = max(1, max_chars_per_chunk)
    for chunk in chunks:
        if remaining <= 0:
            warnings.append("llm_request_truncated:max_total_chars_per_llm_request")
            break
        text = clean_space(chunk.text)
        allowed = min(per_chunk_limit, remaining)
        if len(text) > allowed:
            text = text[:allowed]
            warnings.append(f"llm_chunk_truncated:{chunk.chunk_index}")
        remaining -= len(text)
        limited.append(
            SemanticChunk(
                page_url=chunk.page_url,
                page_title=chunk.page_title,
                source_name=chunk.source_name,
                chunk_index=chunk.chunk_index,
                text=text,
                score=chunk.score,
            )
        )
    return limited or list(chunks[:1]), _dedupe(warnings)


def _strip_code_fence(response: str) -> str:
    text = response.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


def _remove_thinking_sections(response: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", response, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(
        r"(?:Thinking Process|Reasoning|Chain[- ]of[- ]thought)\s*:.*?(?=\{)",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return text.strip()


def _first_json_object(response: str) -> str:
    start = response.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(response[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return response[start : index + 1]
    return ""


def _chunks_by_page(
    chunks: Sequence[SemanticChunk],
    *,
    max_pages: int,
    max_chunks: int,
) -> list[list[SemanticChunk]]:
    grouped: dict[str, list[SemanticChunk]] = defaultdict(list)
    order: list[str] = []
    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        if chunk.page_url not in grouped:
            order.append(chunk.page_url)
        grouped[chunk.page_url].append(chunk)
    return [grouped[page_url][:max_chunks] for page_url in order[:max_pages]]


def _matching_candidate(page_url: str, candidates: Sequence[Candidate]) -> Candidate | None:
    for candidate in candidates:
        if page_url == candidate.source_url or bool(candidate.application_link and page_url == candidate.application_link):
            return candidate
    return None


def _with_schema_defaults(parsed: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(_SCHEMA))
    for key in result:
        if key in parsed:
            result[key] = _normalize_parsed_field(key, parsed[key], result[key])
    return _trim_extraction_text(result)


def _normalize_parsed_field(key: str, parsed_value: Any, default_value: Any) -> Any:
    if key in {"confidence", "warnings"}:
        return parsed_value
    if not isinstance(default_value, dict):
        return parsed_value
    if isinstance(parsed_value, dict):
        normalized = dict(parsed_value)
        if "evidence_ids" not in normalized:
            normalized["evidence_ids"] = _coerce_evidence_ids(normalized.get("evidence_id") or normalized.get("evidence_text", []))
        normalized.pop("evidence_text", None)
        normalized.pop("source_url", None)
        normalized.setdefault("resolved_evidence_texts", [])
        return normalized
    value = parsed_value
    if key == "topics" and isinstance(parsed_value, str):
        value = [item.strip() for item in parsed_value.split(",") if item.strip()]
    return {
        "value": value,
        "evidence_ids": [],
        "resolved_evidence_texts": [],
    }


def _trim_extraction_text(extraction: dict[str, Any]) -> dict[str, Any]:
    for value in extraction.values():
        if not isinstance(value, dict):
            continue
        value["evidence_ids"] = _coerce_evidence_ids(value.get("evidence_ids", []))
        value["resolved_evidence_texts"] = [str(item)[:500] for item in value.get("resolved_evidence_texts", []) if str(item).strip()]
        if isinstance(value.get("value"), str):
            value["value"] = value["value"][:500]
    return extraction


def resolve_evidence_texts(extraction: dict[str, Any], evidence_snippets: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(snippet.get("id")): clean_space(str(snippet.get("text", ""))) for snippet in evidence_snippets}
    for value in extraction.values():
        if not isinstance(value, dict):
            continue
        ids = _coerce_evidence_ids(value.get("evidence_ids", []))
        value["evidence_ids"] = ids
        value["resolved_evidence_texts"] = [by_id[evidence_id] for evidence_id in ids if evidence_id in by_id]
    return extraction


def _public_evidence_snippets(snippets: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(snippet.get("id", "")),
            "page_url": str(snippet.get("page_url", "")),
            "text": clean_space(str(snippet.get("text", "")))[:500],
            "signals": [str(signal) for signal in snippet.get("signals", [])],
        }
        for snippet in snippets
    ]


def _coerce_evidence_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip().upper().startswith("E") else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip().upper().startswith("E")]
    return []


def _llm_warnings(extraction: dict[str, Any]) -> list[str]:
    warnings = extraction.get("warnings", []) if isinstance(extraction, dict) else []
    if isinstance(warnings, list):
        return [str(item) for item in warnings if str(item).strip()]
    return []


def _cached_operational_warnings(item: dict[str, Any]) -> list[str]:
    prefixes = (
        "llm_unavailable:",
        "llm_json_parse_failed",
        "llm_request_truncated:",
        "llm_chunk_truncated:",
        "lmstudio_",
        "ollama_",
        "deepseek_",
    )
    return [
        str(warning)
        for warning in item.get("validation_warnings", [])
        if str(warning).startswith(prefixes)
    ]


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
