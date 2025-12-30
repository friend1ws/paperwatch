"""Paper filtering module using sentence embeddings for semantic search."""

import unicodedata
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer, util

from .fetchers.pubmed import Paper
from .config import KeywordsConfig


def normalize_to_ascii(text: str) -> str:
    """Normalize text by removing diacritics (accents).

    Examples:
        "Müller" -> "Muller"
        "José García" -> "Jose Garcia"
    """
    # NFD: 分解形式に変換（ü → u + ¨）
    normalized = unicodedata.normalize("NFD", text)
    # 結合文字（アクセント記号）を除去
    ascii_text = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return ascii_text


# Name suffixes to ignore when extracting last name
NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "md", "phd", "md."}


def extract_name_pair(full_name: str) -> tuple[str, str] | None:
    """Extract (firstname, lastname) from a full name, ignoring middle names and suffixes.

    Handles both formats:
        - "Firstname Lastname" (e.g., PubMed format)
        - "Lastname, Firstname" (e.g., bioRxiv format)

    Examples:
        "Glennis A. Logsdon" -> ("glennis", "logsdon")
        "John B. Smith Jr." -> ("john", "smith")
        "Logsdon, G. A." -> ("g", "logsdon")
        "Eichler, Evan E." -> ("evan", "eichler")
    """
    normalized = normalize_to_ascii(full_name).lower().strip()
    if not normalized:
        return None

    # Check if name is in "Lastname, Firstname" format
    if "," in normalized:
        parts = normalized.split(",", 1)
        lastname = parts[0].strip()
        firstname_part = parts[1].strip() if len(parts) > 1 else ""
        # Get first name (first word after comma, ignoring initials like "E.")
        firstname_parts = firstname_part.split()
        firstname = None
        for part in firstname_parts:
            # Skip single letter initials (e.g., "E.", "A")
            clean_part = part.rstrip(".")
            if len(clean_part) > 1 and clean_part not in NAME_SUFFIXES:
                firstname = clean_part
                break
            elif len(clean_part) == 1:
                # Use initial if no full name found
                if firstname is None:
                    firstname = clean_part
        if firstname is None:
            firstname = lastname  # Fallback
        return (firstname, lastname)

    # Standard "Firstname Lastname" format
    parts = normalized.split()
    if not parts:
        return None

    firstname = parts[0]

    # Find last name by skipping suffixes from the end
    lastname = None
    for part in reversed(parts[1:]):
        if part not in NAME_SUFFIXES:
            lastname = part
            break

    if lastname is None:
        # Only one name part or all remaining are suffixes
        lastname = firstname

    return (firstname, lastname)


@dataclass
class EmbeddingFilterResult:
    """Result of filtering a paper using embeddings."""
    paper: Paper
    matched_topics: list[str]
    matched_authors: list[str]
    topic_scores: dict[str, float]

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
            topic_strs = [f"{t} ({self.topic_scores.get(t, 0):.2f})" for t in self.matched_topics]
            reasons.append(f"Topics: {', '.join(topic_strs)}")
        return "; ".join(reasons)


class EmbeddingPaperFilter:
    """Filter papers using sentence embeddings for semantic similarity."""

    def __init__(
        self,
        keywords: KeywordsConfig,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.4,
    ):
        """Initialize embedding-based paper filter.

        Args:
            keywords: Keywords configuration with topics and authors.
            model_name: Name of the sentence-transformers model to use.
            similarity_threshold: Minimum cosine similarity to consider a match.
        """
        self.topics = keywords.topics
        self.authors = keywords.authors
        self.similarity_threshold = similarity_threshold

        # Load the embedding model
        print(f"  Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)

        # Pre-compute topic embeddings
        if self.topics:
            self.topic_embeddings = self.model.encode(
                self.topics,
                convert_to_tensor=True,
            )
        else:
            self.topic_embeddings = None

    def filter_paper(self, paper: Paper) -> EmbeddingFilterResult:
        """Filter a single paper using embedding similarity.

        Args:
            paper: Paper to filter.

        Returns:
            EmbeddingFilterResult with match information.
        """
        matched_topics = []
        matched_authors = []
        topic_scores = {}

        # Check topics using embedding similarity
        if self.topic_embeddings is not None:
            paper_text = f"{paper.title} {paper.abstract}"
            paper_embedding = self.model.encode(paper_text, convert_to_tensor=True)

            # Calculate cosine similarity with each topic
            similarities = util.cos_sim(paper_embedding, self.topic_embeddings)[0]

            for i, topic in enumerate(self.topics):
                score = float(similarities[i])
                topic_scores[topic] = score
                if score >= self.similarity_threshold:
                    matched_topics.append(topic)

        # Check authors (use normalized ASCII for comparison)
        # Extract (firstname, lastname) pairs from paper authors
        paper_author_pairs = []
        for author_name in paper.authors:
            pair = extract_name_pair(author_name)
            if pair:
                paper_author_pairs.append(pair)

        for author in self.authors:
            # Extract first and last name from search author
            search_pair = extract_name_pair(author)
            if not search_pair:
                continue

            search_first, search_last = search_pair

            # Check each paper author for a match
            for paper_first, paper_last in paper_author_pairs:
                # Last names must match exactly
                if paper_last != search_last:
                    continue

                # First names match if:
                # 1. Exact match (glennis == glennis)
                # 2. Initial match (g == glennis[0] or glennis == g[0])
                if paper_first == search_first:
                    matched_authors.append(author)
                    break
                elif len(paper_first) == 1 and search_first.startswith(paper_first):
                    # Paper has initial, search has full name
                    matched_authors.append(author)
                    break
                elif len(search_first) == 1 and paper_first.startswith(search_first):
                    # Search has initial, paper has full name
                    matched_authors.append(author)
                    break

        return EmbeddingFilterResult(
            paper=paper,
            matched_topics=matched_topics,
            matched_authors=matched_authors,
            topic_scores=topic_scores,
        )

    def filter_papers(self, papers: list[Paper]) -> list[EmbeddingFilterResult]:
        """Filter multiple papers.

        Args:
            papers: List of papers to filter.

        Returns:
            List of EmbeddingFilterResults for papers that matched.
        """
        results = []
        for paper in papers:
            result = self.filter_paper(paper)
            if result.is_matched:
                results.append(result)
        return results


def filter_papers_by_embedding(
    papers: list[Paper],
    keywords: KeywordsConfig,
    similarity_threshold: float = 0.4,
) -> list[EmbeddingFilterResult]:
    """Convenience function to filter papers using embeddings.

    Args:
        papers: List of papers to filter.
        keywords: Keywords configuration.
        similarity_threshold: Minimum cosine similarity to consider a match.

    Returns:
        List of EmbeddingFilterResults for papers that matched.
    """
    paper_filter = EmbeddingPaperFilter(
        keywords,
        similarity_threshold=similarity_threshold,
    )
    return paper_filter.filter_papers(papers)
