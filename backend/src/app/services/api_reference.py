"""Call the endpoint(s) named in an API checker task and measure them in plain code.

The model's own fetch tool summarises response bodies, so keys and types it reports can be
incomplete or wrong. This does the GET calls directly: real status, timing, every key with its
type, and a test of the common filter/pagination parameters, stored as structured data that the
run page shows as a Swagger-style table.
"""

import asyncio
import ipaddress
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.integrations.http_probe import HttpProbe
from app.schemas.runs import ApiEffect, ApiField, ApiParam, ApiReference

_URL = re.compile(r"https?://[^\s<>\"'`)\]]+")
MAX_URLS = 3
MAX_FIELDS = 300
_ARRAY_SAMPLE = 25
_CONCURRENCY = 4

# (name, value). Values are chosen so a working filter visibly changes the result: a made-up
# search/category should match nothing, page/limit/offset change the window.
CANDIDATE_PARAMS: list[tuple[str, str]] = [
    ("page", "2"),
    ("limit", "5"),
    ("pageSize", "5"),
    ("per_page", "5"),
    ("offset", "5"),
    ("sort", "price"),
    ("sortBy", "price"),
    ("order", "desc"),
    ("search", "zzzxqy"),
    ("q", "zzzxqy"),
    ("query", "zzzxqy"),
    ("name", "zzzxqy"),
    ("category", "zzz-nonexistent"),
    ("categoryId", "zzz-nonexistent"),
    ("tag", "zzz-nonexistent"),
    ("minPrice", "500"),
    ("maxPrice", "1000"),
    ("isAvailable", "false"),
]
_LIST_KEYS = ("data", "items", "results", "products", "records", "rows")
_TOTAL_KEYS = ("total", "totalcount", "total_count", "count", "totalitems", "total_items")


def extract_urls(task: str) -> list[str]:
    seen: list[str] = []
    for match in _URL.findall(task):
        url = match.rstrip(".,;")
        if url not in seen and _is_public_http(url):
            seen.append(url)
    return seen[:MAX_URLS]


def _is_public_http(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return bool(host)
    return not (ip.is_link_local or ip.is_multicast or ip.is_unspecified)


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object"


def flatten(
    value: Any, path: str = "", out: dict[str, dict[str, Any]] | None = None
) -> dict[str, dict[str, Any]]:
    """Every key path -> {types, example}. Arrays are merged across their first elements."""
    out = {} if out is None else out
    if path:
        row = out.setdefault(path, {"types": [], "example": None})
        name = _type_name(value)
        if name not in row["types"]:
            row["types"].append(name)
        if row["example"] is None and value is not None and not isinstance(value, dict | list):
            row["example"] = value
    if isinstance(value, dict):
        for key, child in value.items():
            flatten(child, f"{path}.{key}" if path else str(key), out)
    elif isinstance(value, list):
        for child in value[:_ARRAY_SAMPLE]:
            flatten(child, f"{path}[]", out)
    return out


def _example(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ")
    return text if len(text) <= 40 else text[:37] + "..."


def fields_of(body: Any) -> list[ApiField]:
    rows = flatten(body)
    return [
        ApiField(key=key, type=" or ".join(row["types"]), example=_example(row["example"]))
        for key, row in list(rows.items())[:MAX_FIELDS]
    ]


def main_list(body: Any) -> list[Any] | None:
    """The list of items a listing endpoint returns (the body itself, or its main list key)."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in _LIST_KEYS:
            found = body.get(key)
            if isinstance(found, list):
                return found
        for value in body.values():
            if isinstance(value, list):
                return value
    return None


def total_of(body: Any) -> int | None:
    """A total count reported at the top level or one level down (e.g. `pagination.total`)."""
    if not isinstance(body, dict):
        return None
    for level in [body, *[v for v in body.values() if isinstance(v, dict)]]:
        for key, value in level.items():
            if (
                key.lower() in _TOTAL_KEYS
                and isinstance(value, int)
                and not isinstance(value, bool)
            ):
                return value
    return None


def _ids(items: list[Any]) -> list[str]:
    return [
        str(item["id"])
        if isinstance(item, dict) and "id" in item
        else json.dumps(item, sort_keys=True)
        for item in items
    ]


def compare(baseline: Any, variant: Any) -> tuple[ApiEffect, str]:
    """(effect, detail) of one parameter, comparing the response with the plain one."""
    base_items, new_items = main_list(baseline), main_list(variant)
    base_total, new_total = total_of(baseline), total_of(variant)
    if base_items is None or new_items is None:
        same = baseline == variant
        return ("no visible effect", "") if same else ("changes result", "response differs")
    base_ids, new_ids = _ids(base_items), _ids(new_items)
    notes: list[str] = []
    if len(base_ids) != len(new_ids):
        notes.append(f"{len(base_ids)} to {len(new_ids)} items")
    if base_total is not None and new_total is not None and base_total != new_total:
        notes.append(f"total {base_total} to {new_total}")
    if notes:
        return "changes result", ", ".join(notes)
    if base_ids != new_ids:
        if sorted(base_ids) == sorted(new_ids):
            return "changes order", "same items, different order"
        return "changes result", "different items"
    return "no visible effect", ""


def with_param(url: str, name: str, value: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != name]
    query.append((name, value))
    return urlunsplit(parts._replace(query=urlencode(query)))


async def _probe_param(
    probe: HttpProbe, url: str, name: str, value: str, baseline: Any, sem: asyncio.Semaphore
) -> ApiParam:
    async with sem:
        try:
            response = await probe.get(with_param(url, name, value), headers=_HEADERS)
        except httpx.HTTPError as exc:
            return ApiParam(name=name, value=value, effect="error", detail=type(exc).__name__)
    if response.status_code >= 400:
        return ApiParam(
            name=name, value=value, effect="rejected", detail=f"HTTP {response.status_code}"
        )
    try:
        body = response.json()
    except ValueError:
        return ApiParam(name=name, value=value, effect="error", detail="not JSON")
    effect, detail = compare(baseline, body)
    return ApiParam(name=name, value=value, effect=effect, detail=detail)


_HEADERS = {"Accept": "application/json"}


async def build_reference(probe: HttpProbe, url: str, out_dir: Path, n: int) -> ApiReference:
    started = time.monotonic()
    try:
        response = await probe.get(url, headers=_HEADERS)
    except httpx.HTTPError as exc:
        return ApiReference(url=url, error=f"No answer ({type(exc).__name__})")
    ref = ApiReference(
        url=url,
        status=response.status_code,
        content_type=response.headers.get("content-type", ""),
        time_ms=int((time.monotonic() - started) * 1000),
        size_bytes=len(response.content),
    )
    try:
        body = response.json()
    except ValueError:
        return ref
    ref.is_json = True
    items = main_list(body)
    ref.item_count = len(items) if items is not None else None
    ref.total = total_of(body)
    ref.fields = fields_of(body)
    raw = out_dir / f"response-{n}.json"
    raw.write_text(json.dumps(body, indent=2, ensure_ascii=False))
    ref.raw_file = raw.name
    if response.status_code < 400:
        tried = {k for k, _ in parse_qsl(urlsplit(url).query)}
        sem = asyncio.Semaphore(_CONCURRENCY)
        ref.params = list(
            await asyncio.gather(
                *[
                    _probe_param(probe, url, name, value, body, sem)
                    for name, value in CANDIDATE_PARAMS
                    if name not in tried
                ]
            )
        )
    return ref


async def build_references(task: str, probe: HttpProbe, out_dir: Path) -> list[ApiReference]:
    return [
        await build_reference(probe, url, out_dir, n)
        for n, url in enumerate(extract_urls(task), start=1)
    ]


def agent_notes(refs: list[ApiReference]) -> list[str]:
    """Short prompt lines so the agent doesn't redo (or contradict) what was measured."""
    lines: list[str] = []
    for ref in refs:
        if ref.error:
            lines.append(f"- {ref.url}: {ref.error}")
            continue
        works = [p.name for p in ref.params if p.effect.startswith("changes")]
        lines.append(
            f"- {ref.url}: HTTP {ref.status}, {len(ref.fields)} keys, "
            f"{ref.item_count} items, total {ref.total}. Parameters that changed the response: "
            f"{', '.join(works) or 'none of the common ones'}."
        )
    return lines
