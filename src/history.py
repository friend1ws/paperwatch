"""Track notified papers to prevent duplicate notifications."""

import json
from datetime import datetime, timedelta
from pathlib import Path


class NotificationHistory:
    """Track which papers have been notified to prevent duplicates."""

    def __init__(self, history_file: str | Path = "notified_papers.json"):
        """Initialize notification history.

        Args:
            history_file: Path to the JSON file storing notified paper IDs.
        """
        self.history_file = Path(history_file)
        self.notified: dict[str, str] = {}  # paper_id -> notification_date
        self._load()

    def _load(self) -> None:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    self.notified = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.notified = {}

    def save(self) -> None:
        """Save history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(self.notified, f, indent=2, sort_keys=True)

    def is_notified(self, paper_id: str) -> bool:
        """Check if a paper has already been notified.

        Args:
            paper_id: Unique identifier for the paper (PMID or DOI-based).

        Returns:
            True if paper was already notified.
        """
        return paper_id in self.notified

    def mark_notified(self, paper_ids: list[str]) -> None:
        """Mark papers as notified.

        Args:
            paper_ids: List of paper IDs to mark as notified.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        for paper_id in paper_ids:
            self.notified[paper_id] = today

    def cleanup_old(self, days: int = 90) -> int:
        """Remove entries older than specified days.

        Args:
            days: Number of days to keep history.

        Returns:
            Number of entries removed.
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        old_count = len(self.notified)
        self.notified = {
            k: v for k, v in self.notified.items()
            if v >= cutoff_str
        }
        return old_count - len(self.notified)

    def filter_new(self, papers: list) -> list:
        """Filter out already notified papers.

        Args:
            papers: List of papers (must have 'pmid' attribute).

        Returns:
            List of papers that haven't been notified yet.
        """
        return [p for p in papers if not self.is_notified(p.pmid)]
