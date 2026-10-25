"""Full-text enrichment for selected papers."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Optional
from xml.etree import ElementTree as ET

import httpx

from .fetchers.pubmed import Paper


HTTP_HEADERS = {
    "User-Agent": "paperwatch/0.1 (+https://github.com/friend1ws/paperwatch)",
}
FULL_TEXT_TOPIC_THRESHOLD = 0.55
MAX_FULL_TEXT_PAPERS = 3
MAX_FULL_TEXT_CHARS = 35000
MAX_PDF_PAGES = 25


def _max_topic_score(result: Any) -> float:
    scores = getattr(result, "topic_scores", {}) or {}
    return max(scores.values(), default=0.0)


def _should_try_full_text(result: Any) -> bool:
    paper = getattr(result, "paper", None)
    if paper is None or not _supports_full_text(paper):
        return False
    if getattr(result, "matched_authors", None):
        return True
    return _max_topic_score(result) >= FULL_TEXT_TOPIC_THRESHOLD


def _supports_full_text(paper: Paper) -> bool:
    return paper.source in {"biorxiv", "medrxiv"}


def select_full_text_candidates(
    filter_results: list[Any],
    max_papers: int = MAX_FULL_TEXT_PAPERS,
) -> list[Any]:
    """Select the highest-priority papers for full-text enrichment."""
    candidates = [result for result in filter_results if _should_try_full_text(result)]

    def sort_key(result: Any) -> tuple[int, float]:
        has_author_match = bool(getattr(result, "matched_authors", None))
        return (1 if has_author_match else 0, _max_topic_score(result))

    return sorted(candidates, key=sort_key, reverse=True)[:max_papers]


def enrich_full_texts(
    filter_results: list[Any],
    max_papers: int = MAX_FULL_TEXT_PAPERS,
) -> int:
    """Fetch full text for selected papers when available.

    The function mutates each selected result's ``paper`` object by setting
    ``full_text`` and ``full_text_source``. Papers that cannot be enriched keep
    using their abstract during summarization.
    """
    selected = select_full_text_candidates(filter_results, max_papers=max_papers)
    if not selected:
        print("  Full text: no papers met full-text criteria")
        return 0

    print(f"  Full text: trying {len(selected)} selected paper(s)")
    enriched_count = 0
    with httpx.Client(
        timeout=45.0,
        follow_redirects=True,
        headers=HTTP_HEADERS,
    ) as client:
        for result in selected:
            paper = result.paper
            text, source = fetch_full_text(paper, client)
            if text:
                paper.full_text = text
                paper.full_text_source = source
                enriched_count += 1
                print(f"    + {paper.title[:60]}... ({source})")
            else:
                paper.full_text_source = "abstract only"
                print(f"    - {paper.title[:60]}... (abstract only)")

    print(f"  Full text: enriched {enriched_count}/{len(selected)} paper(s)")
    return enriched_count


def fetch_full_text(
    paper: Paper,
    client: httpx.Client,
) -> tuple[Optional[str], Optional[str]]:
    """Fetch full text for a paper, returning ``(text, source)``."""
    if paper.source in {"biorxiv", "medrxiv"}:
        return fetch_biorxiv_full_text(paper, client)
    return None, None


def fetch_biorxiv_full_text(
    paper: Paper,
    client: httpx.Client,
) -> tuple[Optional[str], Optional[str]]:
    """Fetch bioRxiv/medRxiv full text, preferring JATS XML over PDF."""
    if paper.jats_xml_path:
        text = _fetch_jats_text(paper, client)
        if text:
            return text, f"{paper.source} JATS"

    text = _fetch_pdf_text(paper, client)
    if text:
        return text, f"{paper.source} PDF"

    return None, None


def _fetch_jats_text(paper: Paper, client: httpx.Client) -> Optional[str]:
    url = _resolve_jats_url(paper)
    if not url:
        return None

    try:
        response = client.get(url)
        response.raise_for_status()
        return _trim_for_llm(_extract_jats_body(response.text))
    except Exception as e:
        print(f"    JATS fetch failed for {paper.doi}: {e}")
        return None


def _resolve_jats_url(paper: Paper) -> Optional[str]:
    if not paper.jats_xml_path:
        return None
    if paper.jats_xml_path.startswith(("http://", "https://")):
        return paper.jats_xml_path

    domain = "www.medrxiv.org" if paper.source == "medrxiv" else "www.biorxiv.org"
    path = paper.jats_xml_path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"https://{domain}{path}"


def _fetch_pdf_text(paper: Paper, client: httpx.Client) -> Optional[str]:
    url = _build_pdf_url(paper)
    if not url:
        return None

    try:
        response = client.get(url)
        response.raise_for_status()
        return _trim_for_llm(_extract_pdf_text(response.content))
    except ImportError:
        print("    PDF extraction skipped: install pypdf")
        return None
    except Exception as e:
        print(f"    PDF fetch failed for {paper.doi}: {e}")
        return None


def _build_pdf_url(paper: Paper) -> Optional[str]:
    if not paper.doi:
        return None

    version = paper.version or "1"
    doi = paper.doi
    if re.search(r"v\d+$", doi):
        doi_with_version = doi
    else:
        doi_with_version = f"{doi}v{version}"

    domain = "www.medrxiv.org" if paper.source == "medrxiv" else "www.biorxiv.org"
    return f"https://{domain}/content/{doi_with_version}.full.pdf"


def _extract_jats_body(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    body = _find_first(root, "body")
    if body is None:
        body = root

    chunks = []
    for element in body.iter():
        tag = _local_name(element.tag)
        if tag in {"title", "p"}:
            text = _element_text(element)
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


def _trim_for_llm(text: str) -> str:
    text = _clean_text(text)
    text = _drop_back_matter(text)
    if len(text) > MAX_FULL_TEXT_CHARS:
        text = text[:MAX_FULL_TEXT_CHARS].rsplit("\n", 1)[0].strip()
        text += "\n\n[Full text truncated before summarization.]"
    return text


def _clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _drop_back_matter(text: str) -> str:
    pattern = re.compile(
        r"\n\s*(references|bibliography|acknowledg(e)?ments|author contributions|"
        r"competing interests)\s*\n",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return text
    return text[: match.start()].strip()


def _find_first(root: ET.Element, local_name: str) -> Optional[ET.Element]:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            return element
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element) -> str:
    return " ".join(part.strip() for part in element.itertext() if part.strip())
