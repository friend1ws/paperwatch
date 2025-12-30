"""bioRxiv and medRxiv fetcher using their public API."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .pubmed import Paper


class BioRxivFetcher:
    """Fetcher for bioRxiv and medRxiv preprints."""

    BASE_URL = "https://api.biorxiv.org/details"

    def __init__(self):
        """Initialize bioRxiv fetcher."""
        self.client = httpx.Client(timeout=30.0)

    def fetch_papers(
        self,
        server: str = "biorxiv",
        days_back: int = 1,
        max_results: int = 2000,
        categories: list[str] | None = None,
    ) -> list[Paper]:
        """Fetch recent preprints from bioRxiv or medRxiv.

        Args:
            server: Either "biorxiv" or "medrxiv".
            days_back: Number of days back to search.
            max_results: Maximum number of results to return.
            categories: List of categories to filter by (None = all categories).

        Returns:
            List of Paper objects.
        """
        # Normalize category names for comparison
        if categories:
            categories_lower = [c.lower() for c in categories]
        else:
            categories_lower = None

        # Date filter (target: days_back days before today, excluding today)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today - timedelta(days=1)  # Yesterday
        start_date = today - timedelta(days=days_back)  # days_back days ago

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # API endpoint: /details/{server}/{start_date}/{end_date}/{cursor}
        url = f"{self.BASE_URL}/{server}/{start_str}/{end_str}/0"

        papers = []
        cursor = 0

        while len(papers) < max_results:
            url = f"{self.BASE_URL}/{server}/{start_str}/{end_str}/{cursor}"
            response = self.client.get(url)
            response.raise_for_status()

            data = response.json()
            collection = data.get("collection", [])

            if not collection:
                break

            for item in collection:
                # Filter by category if specified
                if categories_lower:
                    item_category = item.get("category", "").lower()
                    if item_category not in categories_lower:
                        continue

                paper = self._parse_preprint(item, server)
                if paper:
                    papers.append(paper)

                if len(papers) >= max_results:
                    break

            # Check if there are more results
            messages = data.get("messages", [{}])
            if messages:
                total = int(messages[0].get("total", 0))
                cursor += len(collection)
                if cursor >= total:
                    break
            else:
                break

        return papers

    def _parse_preprint(self, item: dict, server: str) -> Optional[Paper]:
        """Parse a single preprint from API response.

        Args:
            item: Dictionary containing preprint data.
            server: Server name (biorxiv or medrxiv).

        Returns:
            Paper object or None if parsing fails.
        """
        try:
            doi = item.get("doi", "")
            title = item.get("title", "")
            authors_str = item.get("authors", "")
            abstract = item.get("abstract", "")
            pub_date = item.get("date", "")
            category = item.get("category", "")

            # Parse authors (format: "Author1, Author2, Author3")
            authors = [a.strip() for a in authors_str.split(";") if a.strip()]

            # Use DOI as the identifier
            pmid = doi.replace("/", "_")  # Create a unique ID from DOI

            return Paper(
                pmid=pmid,
                title=title,
                authors=authors,
                abstract=abstract,
                journal=f"{server} ({category})" if category else server,
                pub_date=pub_date,
                doi=doi,
                source=server,
            )
        except Exception as e:
            print(f"Error parsing preprint: {e}")
            return None

    def fetch_all_preprints(
        self,
        servers: list[str],
        days_back: int = 1,
        max_results_per_server: int = 2000,
        categories_by_server: dict[str, list[str]] | None = None,
    ) -> list[Paper]:
        """Fetch preprints from multiple servers.

        Args:
            servers: List of servers ("bioRxiv", "medRxiv").
            days_back: Number of days back to search.
            max_results_per_server: Maximum results per server.
            categories_by_server: Dict mapping server name to list of categories.

        Returns:
            Combined list of Paper objects.
        """
        all_papers = []
        categories_by_server = categories_by_server or {}

        for server in servers:
            # Normalize server name
            server_lower = server.lower().replace("rxiv", "rxiv")
            if server_lower in ["biorxiv", "medrxiv"]:
                # Get categories for this server
                server_categories = categories_by_server.get(server_lower)
                papers = self.fetch_papers(
                    server=server_lower,
                    days_back=days_back,
                    max_results=max_results_per_server,
                    categories=server_categories,
                )
                all_papers.extend(papers)

        return all_papers

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
