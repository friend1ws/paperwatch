"""Paper filtering module based on keywords and authors."""

import re
from dataclasses import dataclass

from .fetchers.pubmed import Paper
from .config import KeywordsConfig


@dataclass
class FilterResult:
    """Result of filtering a paper."""
    paper: Paper
    matched_topics: list[str]
    matched_authors: list[str]

    @property
    def is_matched(self) -> bool:
        """Check if paper matched any filter."""
        return bool(self.matched_topics or self.matched_authors)

    @property
    def match_reason(self) -> str:
        """Get human-readable match reason."""
        reasons = []
        if self.matched_authors:
            reasons.append(f"Authors: {', '.join(self.matched_authors)}")
        if self.matched_topics:
            reasons.append(f"Topics: {', '.join(self.matched_topics)}")
        return "; ".join(reasons)


class PaperFilter:
    """Filter papers based on keywords and authors."""

    def __init__(self, keywords: KeywordsConfig):
        """Initialize paper filter.

        Args:
            keywords: Keywords configuration with topics and authors.
        """
        self.topics = keywords.topics
        self.authors = keywords.authors

        # Pre-compile topic patterns (case-insensitive)
        self.topic_patterns = [
            re.compile(rf"\b{re.escape(topic)}\b", re.IGNORECASE)
            for topic in self.topics
        ]

        # Pre-compile author patterns (case-insensitive)
        # Match full name or last name
        self.author_patterns = []
        for author in self.authors:
            # Full name match
            self.author_patterns.append(
                (author, re.compile(rf"\b{re.escape(author)}\b", re.IGNORECASE))
            )
            # Last name match (assume last word is surname)
            parts = author.split()
            if len(parts) > 1:
                lastname = parts[-1]
                self.author_patterns.append(
                    (author, re.compile(rf"\b{re.escape(lastname)}\b", re.IGNORECASE))
                )

    def filter_paper(self, paper: Paper) -> FilterResult:
        """Filter a single paper.

        Args:
            paper: Paper to filter.

        Returns:
            FilterResult with match information.
        """
        matched_topics = []
        matched_authors = []

        # Check topics in title and abstract
        searchable_text = f"{paper.title} {paper.abstract}"

        for topic, pattern in zip(self.topics, self.topic_patterns):
            if pattern.search(searchable_text):
                matched_topics.append(topic)

        # Check authors
        authors_text = " ".join(paper.authors)
        matched_author_names = set()

        for author_name, pattern in self.author_patterns:
            if pattern.search(authors_text):
                matched_author_names.add(author_name)

        matched_authors = list(matched_author_names)

        return FilterResult(
            paper=paper,
            matched_topics=matched_topics,
            matched_authors=matched_authors,
        )

    def filter_papers(self, papers: list[Paper]) -> list[FilterResult]:
        """Filter multiple papers.

        Args:
            papers: List of papers to filter.

        Returns:
            List of FilterResults for papers that matched.
        """
        results = []
        for paper in papers:
            result = self.filter_paper(paper)
            if result.is_matched:
                results.append(result)
        return results


def filter_papers_by_keywords(papers: list[Paper], keywords: KeywordsConfig) -> list[FilterResult]:
    """Convenience function to filter papers.

    Args:
        papers: List of papers to filter.
        keywords: Keywords configuration.

    Returns:
        List of FilterResults for papers that matched.
    """
    paper_filter = PaperFilter(keywords)
    return paper_filter.filter_papers(papers)
