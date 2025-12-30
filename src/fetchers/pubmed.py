"""PubMed fetcher using NCBI E-utilities API."""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from xml.etree import ElementTree as ET

import httpx


@dataclass
class Paper:
    """Represents a research paper."""
    pmid: str
    title: str
    authors: list[str]
    abstract: str
    journal: str
    pub_date: str
    doi: Optional[str] = None
    source: str = "pubmed"

    @property
    def url(self) -> str:
        """Return URL to the paper."""
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


class PubMedFetcher:
    """Fetcher for PubMed papers using E-utilities API."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    SEARCH_URL = f"{BASE_URL}/esearch.fcgi"
    FETCH_URL = f"{BASE_URL}/efetch.fcgi"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize PubMed fetcher.

        Args:
            api_key: Optional NCBI API key for higher rate limits.
        """
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def _build_search_query(
        self,
        journals: list[str],
        days_back: int = 1,
    ) -> str:
        """Build PubMed search query.

        Args:
            journals: List of journal names to search.
            days_back: Number of days back to search.

        Returns:
            PubMed query string.
        """
        # Build journal filter
        journal_queries = []
        for journal in journals:
            journal_queries.append(f'"{journal}"[Journal]')

        journal_filter = " OR ".join(journal_queries)

        # Build date filter (target: days_back days before today, excluding today)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today - timedelta(days=1)  # Yesterday
        start_date = today - timedelta(days=days_back)  # days_back days ago
        date_filter = f'("{start_date.strftime("%Y/%m/%d")}"[Date - Publication] : "{end_date.strftime("%Y/%m/%d")}"[Date - Publication])'

        # Combine filters
        query = f"({journal_filter}) AND {date_filter}"
        return query

    def search(
        self,
        journals: list[str],
        days_back: int = 1,
        max_results: int = 500,
    ) -> list[str]:
        """Search PubMed for recent papers.

        Args:
            journals: List of journal names to search.
            days_back: Number of days back to search.
            max_results: Maximum number of results to return.

        Returns:
            List of PubMed IDs (PMIDs).
        """
        query = self._build_search_query(journals, days_back)

        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "pub_date",
        }

        if self.api_key:
            params["api_key"] = self.api_key

        response = self.client.get(self.SEARCH_URL, params=params)
        response.raise_for_status()

        data = response.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        return pmids

    def fetch_details(self, pmids: list[str], batch_size: int = 200) -> list[Paper]:
        """Fetch paper details for given PMIDs.

        Args:
            pmids: List of PubMed IDs.
            batch_size: Number of PMIDs to fetch per request.

        Returns:
            List of Paper objects.
        """
        if not pmids:
            return []

        all_papers = []

        # Process PMIDs in batches to avoid URL length limits
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]

            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            }

            if self.api_key:
                params["api_key"] = self.api_key

            response = self.client.get(self.FETCH_URL, params=params)
            response.raise_for_status()

            papers = self._parse_xml_response(response.text)
            all_papers.extend(papers)

            # Rate limiting between batches
            if not self.api_key and i + batch_size < len(pmids):
                time.sleep(0.34)

        return all_papers

    def _parse_xml_response(self, xml_text: str) -> list[Paper]:
        """Parse PubMed XML response.

        Args:
            xml_text: XML response from PubMed.

        Returns:
            List of Paper objects.
        """
        papers = []
        root = ET.fromstring(xml_text)

        for article in root.findall(".//PubmedArticle"):
            try:
                paper = self._parse_article(article)
                if paper:
                    papers.append(paper)
            except Exception as e:
                # Log error but continue processing other articles
                print(f"Error parsing article: {e}")
                continue

        return papers

    def _parse_article(self, article: ET.Element) -> Optional[Paper]:
        """Parse a single PubMed article.

        Args:
            article: XML element for a PubMed article.

        Returns:
            Paper object or None if parsing fails.
        """
        medline = article.find(".//MedlineCitation")
        if medline is None:
            return None

        # Get PMID
        pmid_elem = medline.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # Get article info
        article_elem = medline.find(".//Article")
        if article_elem is None:
            return None

        # Get title
        title_elem = article_elem.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else ""

        # Get abstract
        abstract_elem = article_elem.find(".//Abstract/AbstractText")
        abstract = ""
        if abstract_elem is not None:
            # Handle structured abstracts
            abstract_parts = article_elem.findall(".//Abstract/AbstractText")
            abstract_texts = []
            for part in abstract_parts:
                label = part.get("Label", "")
                text = part.text or ""
                if label:
                    abstract_texts.append(f"{label}: {text}")
                else:
                    abstract_texts.append(text)
            abstract = " ".join(abstract_texts)

        # Get authors
        authors = []
        author_list = article_elem.find(".//AuthorList")
        if author_list is not None:
            for author in author_list.findall(".//Author"):
                lastname = author.find("LastName")
                forename = author.find("ForeName")
                if lastname is not None and forename is not None:
                    authors.append(f"{forename.text} {lastname.text}")
                elif lastname is not None:
                    authors.append(lastname.text)

        # Get journal
        journal_elem = article_elem.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else ""

        # Get publication date
        pub_date_elem = article_elem.find(".//Journal/JournalIssue/PubDate")
        pub_date = ""
        if pub_date_elem is not None:
            year = pub_date_elem.find("Year")
            month = pub_date_elem.find("Month")
            day = pub_date_elem.find("Day")
            parts = []
            if year is not None:
                parts.append(year.text)
            if month is not None:
                parts.append(month.text)
            if day is not None:
                parts.append(day.text)
            pub_date = " ".join(parts)

        # Get DOI
        doi = None
        article_id_list = article.find(".//PubmedData/ArticleIdList")
        if article_id_list is not None:
            for article_id in article_id_list.findall("ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text
                    break

        return Paper(
            pmid=pmid,
            title=title,
            authors=authors,
            abstract=abstract,
            journal=journal,
            pub_date=pub_date,
            doi=doi,
            source="pubmed",
        )

    def fetch_papers(
        self,
        journals: list[str],
        days_back: int = 1,
        max_results: int = 500,
    ) -> list[Paper]:
        """Fetch recent papers from specified journals.

        Args:
            journals: List of journal names to search.
            days_back: Number of days back to search.
            max_results: Maximum number of results to return.

        Returns:
            List of Paper objects.
        """
        pmids = self.search(journals, days_back, max_results)

        if not pmids:
            return []

        # Rate limiting: wait 0.34s between requests (3 requests/second without API key)
        if not self.api_key:
            time.sleep(0.34)

        return self.fetch_details(pmids)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
