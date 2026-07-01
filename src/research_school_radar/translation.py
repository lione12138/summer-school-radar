from __future__ import annotations

import json
import os
import re
import copy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

from .ai_cache import AICache
from .llm_client import BaseLLMClient, LLMClientConfig, create_llm_client
from .models import Candidate
from .utils import ROOT, clean_space, content_hash, load_yaml


TRANSLATION_FIELDS = (
    "title",
    "summary",
    "eligibility",
    "recommendation_reason",
    "risk_points",
)
TRANSLATION_SCHEMA_VERSION = "candidate-zh-v1"
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_EXACT_PROTECTED_RE = re.compile(
    r"https?://\S+|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_CURRENCY_RE = re.compile(
    r"(?:(?:EUR|USD|GBP|CHF|CNY|RMB|JPY|INR|KRW|SGD|AUD|CAD)\s?|[€$£]\s?)(\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class TranslationConfig:
    enabled: bool = False
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    fallback_model: str = ""
    api_key: str = ""
    temperature: float = 0
    timeout_seconds: int = 90
    max_tokens: int = 3000
    max_attempts: int = 2
    cache_enabled: bool = True
    cache_directory: Path = ROOT / "data" / "translation_cache"
    refresh_cache: bool = False
    prompt_version: str = TRANSLATION_SCHEMA_VERSION

    def client_config(self) -> LLMClientConfig:
        return LLMClientConfig(
            provider=self.provider,
            base_url=self.base_url,
            model=self.model,
            fallback_model=self.fallback_model,
            api_key=self.api_key,
            temperature=self.temperature,
            timeout_seconds=self.timeout_seconds,
            max_tokens=self.max_tokens,
        )


@dataclass(slots=True)
class TranslationResult:
    candidates: list[Candidate]
    translated: int = 0
    cache_hits: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RecordTranslationResult:
    records: list[dict[str, Any]]
    translated: int = 0
    cache_hits: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def load_translation_config(path: Path, *, data_dir: Path | None = None) -> TranslationConfig:
    raw: dict[str, Any] = {}
    providers: dict[str, Any] = {}
    if path.exists():
        document = load_yaml(path)
        configured = document.get("translation", {})
        if isinstance(configured, dict):
            raw = dict(configured)
        configured_providers = document.get("providers", {})
        if isinstance(configured_providers, dict):
            providers = configured_providers

    provider = str(raw.get("provider", "deepseek")).strip().lower() or "deepseek"
    defaults = providers.get(provider, {})
    if not isinstance(defaults, dict):
        defaults = {}
    base_url = str(raw.get("base_url") or defaults.get("base_url") or "https://api.deepseek.com")
    model = str(raw.get("model") or defaults.get("model") or "deepseek-v4-flash")
    fallback_model = str(raw.get("fallback_model") or defaults.get("fallback_model") or "")
    api_key = str(raw.get("api_key") or defaults.get("api_key") or "")

    # Resolve the secret beside the project that owns this ai.yaml. Tests and
    # alternate configs therefore never inherit an unrelated workspace key.
    project_data = (ROOT / "data").resolve()
    active_data = (data_dir or ROOT / "data").resolve()
    local_env = _load_local_env(path.resolve().parent.parent / ".env") if active_data == project_data else {}
    provider = os.environ.get("TRANSLATION_PROVIDER") or local_env.get("TRANSLATION_PROVIDER") or provider
    base_url = os.environ.get("TRANSLATION_BASE_URL") or local_env.get("TRANSLATION_BASE_URL") or base_url
    model = os.environ.get("TRANSLATION_MODEL") or local_env.get("TRANSLATION_MODEL") or model
    api_key = os.environ.get("TRANSLATION_API_KEY") or local_env.get("TRANSLATION_API_KEY") or api_key
    if provider.lower() == "deepseek":
        base_url = os.environ.get("DEEPSEEK_BASE_URL") or local_env.get("DEEPSEEK_BASE_URL") or base_url
        model = os.environ.get("DEEPSEEK_MODEL") or local_env.get("DEEPSEEK_MODEL") or model
        api_key = os.environ.get("DEEPSEEK_API_KEY") or local_env.get("DEEPSEEK_API_KEY") or api_key

    cache_root = data_dir or ROOT / "data"
    cache_value = str(raw.get("cache_directory", "translation_cache")).strip()
    cache_directory = Path(cache_value)
    if not cache_directory.is_absolute():
        cache_directory = cache_root / cache_directory

    return TranslationConfig(
        enabled=bool(raw.get("enabled", False)),
        provider=provider,
        base_url=base_url,
        model=model,
        fallback_model=fallback_model,
        api_key=api_key,
        temperature=float(raw.get("temperature", 0)),
        timeout_seconds=int(raw.get("timeout_seconds", 90)),
        max_tokens=int(raw.get("max_tokens", 3000)),
        max_attempts=max(1, int(raw.get("max_attempts", 2))),
        cache_enabled=bool(raw.get("cache_enabled", True)),
        cache_directory=cache_directory,
        refresh_cache=bool(raw.get("refresh_cache", False)),
        prompt_version=str(raw.get("prompt_version", TRANSLATION_SCHEMA_VERSION)),
    )


def translate_candidates(
    candidates: Sequence[Candidate],
    config: TranslationConfig,
    *,
    client: BaseLLMClient | None = None,
) -> TranslationResult:
    if not config.enabled:
        return TranslationResult(candidates=[replace(candidate) for candidate in candidates], skipped=len(candidates))

    cache = AICache(
        enabled=config.cache_enabled,
        directory=config.cache_directory,
        refresh=config.refresh_cache,
    )
    if client is None and config.api_key:
        client = create_llm_client(config.client_config())

    result = TranslationResult(candidates=[])
    warned_missing_provider = False
    for candidate in candidates:
        source = _translation_source(candidate)
        current = _current_translations(candidate)
        needed = {
            key: value
            for key, value in source.items()
            if value and not current.get(key) and not _contains_chinese(value)
        }
        for key, value in source.items():
            if value and _contains_chinese(value) and not current.get(key):
                current[key] = value

        if not needed:
            result.candidates.append(_with_translations(candidate, current))
            result.skipped += 1
            continue

        cache_key = translation_cache_key(needed, config)
        cached = cache.get("candidate_zh", cache_key)
        if isinstance(cached, dict):
            try:
                translated = _validate_translation(needed, cached)
            except ValueError:
                translated = None
            if translated is not None:
                current.update(translated)
                result.candidates.append(_with_translations(candidate, current))
                result.cache_hits += 1
                continue

        if client is None:
            result.candidates.append(_with_translations(candidate, current))
            result.skipped += 1
            if not warned_missing_provider:
                result.warnings.append("translation_provider_unavailable:set_DEEPSEEK_API_KEY")
                warned_missing_provider = True
            continue

        try:
            translated = _request_translation(client, needed, config.max_attempts)
        except Exception as exc:  # noqa: BLE001 - translation failure must not abort publishing cached content.
            result.candidates.append(_with_translations(candidate, current))
            result.skipped += 1
            result.warnings.append(
                f"candidate_translation_failed:{content_hash(candidate.source_url or candidate.title)[:12]}:{type(exc).__name__}"
            )
            continue

        cache.set("candidate_zh", cache_key, translated)
        current.update(translated)
        result.candidates.append(_with_translations(candidate, current))
        result.translated += 1

    result.warnings.extend(cache.warnings)
    return result


def translate_source_metadata(
    sources: Sequence[dict[str, Any]],
    config: TranslationConfig,
    *,
    client: BaseLLMClient | None = None,
) -> RecordTranslationResult:
    records = [copy.deepcopy(source) for source in sources]
    if not config.enabled:
        return RecordTranslationResult(records=records, skipped=len(records))

    cache = AICache(
        enabled=config.cache_enabled,
        directory=config.cache_directory,
        refresh=config.refresh_cache,
    )
    if client is None and config.api_key:
        client = create_llm_client(config.client_config())
    result = RecordTranslationResult(records=[])
    warned_missing_provider = False
    for source in records:
        note = clean_space(str(source.get("notes", "")))
        existing = clean_space(str(source.get("notes_zh", "")))
        if not note or existing or _contains_chinese(note):
            if note and not existing and _contains_chinese(note):
                source["notes_zh"] = note
            result.records.append(source)
            result.skipped += 1
            continue
        payload = {"notes": note}
        cache_key = translation_cache_key(payload, config, kind="source-metadata")
        cached = cache.get("source_metadata_zh", cache_key)
        if isinstance(cached, dict):
            try:
                translated = _validate_translation(payload, cached)
            except ValueError:
                translated = None
            if translated is not None:
                source["notes_zh"] = translated["notes"]
                result.records.append(source)
                result.cache_hits += 1
                continue
        if client is None:
            result.records.append(source)
            result.skipped += 1
            if not warned_missing_provider:
                result.warnings.append("source_translation_provider_unavailable:set_DEEPSEEK_API_KEY")
                warned_missing_provider = True
            continue
        try:
            translated = _request_translation(client, payload, config.max_attempts)
        except Exception as exc:  # noqa: BLE001 - retain original source metadata when translation fails.
            result.records.append(source)
            result.skipped += 1
            result.warnings.append(
                f"source_translation_failed:{content_hash(str(source.get('url') or source.get('name')))[:12]}:{type(exc).__name__}"
            )
            continue
        cache.set("source_metadata_zh", cache_key, translated)
        source["notes_zh"] = translated["notes"]
        result.records.append(source)
        result.translated += 1
    result.warnings.extend(cache.warnings)
    return result


def translation_cache_key(
    source: dict[str, str], config: TranslationConfig, *, kind: str = "candidate"
) -> str:
    payload = {
        "kind": kind,
        "source": source,
        "model": config.model,
        "provider": config.provider,
        "prompt_version": config.prompt_version,
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _translation_source(candidate: Candidate) -> dict[str, str]:
    return {field: clean_space(str(getattr(candidate, field, ""))) for field in TRANSLATION_FIELDS}


def _current_translations(candidate: Candidate) -> dict[str, str]:
    return {
        field: clean_space(str(getattr(candidate, f"{field}_zh", "")))
        for field in TRANSLATION_FIELDS
        if clean_space(str(getattr(candidate, f"{field}_zh", "")))
    }


def _with_translations(candidate: Candidate, translated: dict[str, str]) -> Candidate:
    values = {f"{field}_zh": translated.get(field, "") for field in TRANSLATION_FIELDS}
    return replace(candidate, **values)


def _translation_prompt(source: dict[str, str]) -> str:
    example = {key: "对应的简体中文译文" for key in source}
    return (
        "You are translating official research-training listings into concise, natural Simplified Chinese. "
        "Return one valid json object only. Keep exactly the same keys as the input. Preserve URLs, dates, "
        "currency amounts, institution names, programme acronyms, and factual uncertainty. Do not add claims, "
        "advice, marketing language, or markdown. Translate prose by meaning, not word-for-word. Official titles "
        "may retain an established English acronym after the Chinese name.\n"
        f"Example json shape: {json.dumps(example, ensure_ascii=False)}\n"
        f"Input json: {json.dumps(source, ensure_ascii=False)}"
    )


def _request_translation(
    client: BaseLLMClient, source: dict[str, str], max_attempts: int
) -> dict[str, str]:
    last_error: Exception | None = None
    for _ in range(max_attempts):
        try:
            return _validate_translation(source, _parse_json_object(client.complete(_translation_prompt(source))))
        except Exception as exc:  # noqa: BLE001 - retry malformed or incomplete model output.
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("translation request produced no result")


def _parse_json_object(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("translation response is not a JSON object")
    return parsed


def _validate_translation(source: dict[str, str], translated: dict[str, Any]) -> dict[str, str]:
    if set(translated) != set(source):
        raise ValueError("translation keys do not match source keys")
    clean: dict[str, str] = {}
    for key, original in source.items():
        value = clean_space(str(translated.get(key, "")))
        if not value:
            raise ValueError(f"empty translation for {key}")
        for token in _EXACT_PROTECTED_RE.findall(original):
            if token not in value:
                raise ValueError(f"protected token changed in {key}")
        compact_value = value.replace(",", "")
        for amount in _CURRENCY_RE.findall(original):
            if amount.replace(",", "") not in compact_value:
                raise ValueError(f"currency amount changed in {key}")
        clean[key] = value
    return clean


def _contains_chinese(value: str) -> bool:
    return bool(_CJK_RE.search(value))


def _load_local_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
