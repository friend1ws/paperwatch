"""Configuration loader module."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class SearchConfig:
    """Search configuration."""
    days_back: int = 1


@dataclass
class KeywordsConfig:
    """Keywords configuration."""
    topics: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)


@dataclass
class JournalsConfig:
    """Journals configuration."""
    pubmed: list[str] = field(default_factory=list)
    preprint: list[str] = field(default_factory=list)
    preprint_categories: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SlackConfig:
    """Slack configuration."""
    channel: str = "#research-papers"


@dataclass
class Config:
    """Main configuration class."""
    journals: JournalsConfig
    keywords: KeywordsConfig
    search: SearchConfig
    slack: SlackConfig

    # API keys (loaded from environment)
    anthropic_api_key: Optional[str] = None
    slack_bot_token: Optional[str] = None
    pubmed_api_key: Optional[str] = None


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config YAML file. If None, uses default location.

    Returns:
        Config object with all settings.
    """
    if config_path is None:
        # Default to config/config.yaml relative to this file's parent
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse journals
    journals_data = data.get("journals", {})
    journals = JournalsConfig(
        pubmed=journals_data.get("pubmed", []),
        preprint=journals_data.get("preprint", []),
        preprint_categories=journals_data.get("preprint_categories", {}),
    )

    # Parse keywords
    keywords_data = data.get("keywords", {})
    keywords = KeywordsConfig(
        topics=keywords_data.get("topics", []),
        authors=keywords_data.get("authors", []),
    )

    # Parse search config
    search_data = data.get("search", {})
    search = SearchConfig(
        days_back=search_data.get("days_back", 1),
    )

    # Parse slack config
    slack_data = data.get("slack", {})
    slack = SlackConfig(
        channel=slack_data.get("channel", "#research-papers"),
    )

    # Load API keys from environment variables
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    pubmed_api_key = os.environ.get("PUBMED_API_KEY")  # Optional, increases rate limit

    return Config(
        journals=journals,
        keywords=keywords,
        search=search,
        slack=slack,
        anthropic_api_key=anthropic_api_key,
        slack_bot_token=slack_bot_token,
        pubmed_api_key=pubmed_api_key,
    )
