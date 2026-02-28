"""
Context ingestion agent for NBA news + injury feeds.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable, List
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

from src.intelligence.types import ContextDocument

logger = logging.getLogger(__name__)


TEAM_PATTERNS = {
    "ATL": ["atlanta hawks", "hawks"],
    "BOS": ["boston celtics", "celtics"],
    "BKN": ["brooklyn nets", "nets"],
    "CHA": ["charlotte hornets", "hornets"],
    "CHI": ["chicago bulls", "bulls"],
    "CLE": ["cleveland cavaliers", "cavaliers", "cavs"],
    "DAL": ["dallas mavericks", "mavericks", "mavs"],
    "DEN": ["denver nuggets", "nuggets"],
    "DET": ["detroit pistons", "pistons"],
    "GSW": ["golden state warriors", "warriors"],
    "HOU": ["houston rockets", "rockets"],
    "IND": ["indiana pacers", "pacers"],
    "LAC": ["la clippers", "los angeles clippers", "clippers"],
    "LAL": ["la lakers", "los angeles lakers", "lakers"],
    "MEM": ["memphis grizzlies", "grizzlies"],
    "MIA": ["miami heat", "heat"],
    "MIL": ["milwaukee bucks", "bucks"],
    "MIN": ["minnesota timberwolves", "timberwolves", "wolves"],
    "NOP": ["new orleans pelicans", "pelicans"],
    "NYK": ["new york knicks", "knicks"],
    "OKC": ["oklahoma city thunder", "thunder"],
    "ORL": ["orlando magic", "magic"],
    "PHI": ["philadelphia 76ers", "76ers", "sixers"],
    "PHX": ["phoenix suns", "suns"],
    "POR": ["portland trail blazers", "trail blazers", "blazers"],
    "SAC": ["sacramento kings", "kings"],
    "SAS": ["san antonio spurs", "spurs"],
    "TOR": ["toronto raptors", "raptors"],
    "UTA": ["utah jazz", "jazz"],
    "WAS": ["washington wizards", "wizards"],
}


def _strip_html(raw: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


def _extract_team_tags(text: str) -> List[str]:
    lowered = text.lower()
    tags: List[str] = []
    for abbr, aliases in TEAM_PATTERNS.items():
        if any(alias in lowered for alias in aliases):
            tags.append(abbr)
    return tags


def _doc_id(*parts: str) -> str:
    payload = "||".join(parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown-source"
    except Exception:
        return "unknown-source"


def _entry_text(item: ET.Element, tag_names: Iterable[str]) -> str:
    for tag_name in tag_names:
        node = item.find(tag_name)
        if node is not None and node.text:
            return node.text.strip()
    return ""


def parse_feed_content(xml_content: str, source_url: str, max_items: int = 40) -> List[ContextDocument]:
    """
    Parse RSS/Atom XML into normalized ContextDocument rows.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        logger.warning("Skipping malformed feed XML: %s", source_url)
        return []

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    documents: List[ContextDocument] = []
    for item in items[:max_items]:
        title = _entry_text(item, ("title", "{http://www.w3.org/2005/Atom}title"))
        link = _entry_text(item, ("link",))
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = atom_link.attrib.get("href", "")

        published_raw = _entry_text(
            item,
            ("pubDate", "published", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"),
        )
        description = _entry_text(
            item,
            ("description", "summary", "{http://www.w3.org/2005/Atom}summary", "content"),
        )
        content = _strip_html(description)
        if not title and not content:
            continue

        published_at = _parse_datetime(published_raw)
        combined_text = f"{title} {content}".strip()
        team_tags = _extract_team_tags(combined_text)
        player_tags: List[str] = []

        doc_id = _doc_id(title or "untitled", link or source_url, published_at.isoformat())
        documents.append(
            ContextDocument(
                doc_id=doc_id,
                source=_host(source_url),
                title=title or "Untitled NBA context",
                url=link or source_url,
                published_at=published_at,
                team_tags=team_tags,
                player_tags=player_tags,
                content=content or title or "No content",
            )
        )
    return documents


def chunk_context_document(
    doc: ContextDocument,
    *,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> List[ContextDocument]:
    """
    Deterministically split one context document into overlapping char chunks.
    """
    raw_text = (doc.content or "").strip()
    if not raw_text:
        return []

    if chunk_size <= 0:
        chunk_size = 900
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(chunk_size // 4, 1)

    if len(raw_text) <= chunk_size:
        return [doc]

    chunks: List[ContextDocument] = []
    start = 0
    index = 0
    while start < len(raw_text):
        end = min(start + chunk_size, len(raw_text))
        chunk_text = raw_text[start:end].strip()
        if chunk_text:
            chunks.append(
                ContextDocument(
                    doc_id=f"{doc.doc_id}::chunk_{index}",
                    source=doc.source,
                    title=doc.title,
                    url=doc.url,
                    published_at=doc.published_at,
                    team_tags=list(doc.team_tags),
                    player_tags=list(doc.player_tags),
                    content=chunk_text,
                )
            )
            index += 1
        if end >= len(raw_text):
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def fetch_context_documents(
    sources: List[str],
    timeout_seconds: int = 8,
    max_items_per_feed: int = 40,
) -> List[ContextDocument]:
    """
    Fetch and parse configured context feeds.
    """
    docs: List[ContextDocument] = []
    for source in sources:
        try:
            response = requests.get(source, timeout=timeout_seconds)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Skipping source %s due to fetch error: %s", source, exc)
            continue
        docs.extend(parse_feed_content(response.text, source, max_items=max_items_per_feed))
    return docs
