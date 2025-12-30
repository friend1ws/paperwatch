"""Main entry point for research paper notification system."""

import argparse
import os
import sys
from datetime import datetime

from .config import load_config, Config
from .fetchers import PubMedFetcher, BioRxivFetcher
from .fetchers.pubmed import Paper
from .filter_embedding import filter_papers_by_embedding
from .summarizer import summarize_papers
from .notifier import send_to_slack


def fetch_all_papers(config: Config) -> list[Paper]:
    """Fetch papers from all configured sources.

    Args:
        config: Configuration object.

    Returns:
        List of all fetched papers.
    """
    all_papers = []
    days_back = config.search.days_back

    # Fetch from PubMed
    if config.journals.pubmed:
        print(f"Fetching papers from PubMed ({len(config.journals.pubmed)} journals)...")
        with PubMedFetcher(api_key=config.pubmed_api_key) as fetcher:
            papers = fetcher.fetch_papers(
                journals=config.journals.pubmed,
                days_back=days_back,
            )
            print(f"  Found {len(papers)} papers from PubMed")
            all_papers.extend(papers)

    # Fetch from bioRxiv/medRxiv
    if config.journals.preprint:
        print(f"Fetching preprints ({', '.join(config.journals.preprint)})...")
        with BioRxivFetcher() as fetcher:
            papers = fetcher.fetch_all_preprints(
                servers=config.journals.preprint,
                days_back=days_back,
                categories_by_server=config.journals.preprint_categories,
            )
            print(f"  Found {len(papers)} preprints")
            all_papers.extend(papers)

    return all_papers


def run(config_path: str = None, dry_run: bool = False) -> int:
    """Run the paper notification pipeline.

    Args:
        config_path: Path to config file (optional).
        dry_run: If True, don't send to Slack, just print results.

    Returns:
        Exit code (0 for success).
    """
    print("=" * 60)
    print(f"Research Paper Notification - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load configuration
    print("\n[1/5] Loading configuration...")
    config = load_config(config_path)

    # Check if using Bedrock
    use_bedrock = os.environ.get("USE_BEDROCK", "").lower() in ("1", "true", "yes")

    # Validate required settings
    if not dry_run:
        if not use_bedrock and not config.anthropic_api_key:
            print("ERROR: ANTHROPIC_API_KEY environment variable is not set")
            print("  (Set USE_BEDROCK=1 to use AWS Bedrock instead)")
            return 1
        if not config.slack_bot_token:
            print("ERROR: SLACK_BOT_TOKEN environment variable is not set")
            return 1

    if use_bedrock:
        print("  Using AWS Bedrock")

    print(f"  Topics: {', '.join(config.keywords.topics)}")
    print(f"  Authors: {', '.join(config.keywords.authors)}")
    print(f"  Days back: {config.search.days_back}")

    # Fetch papers
    print("\n[2/5] Fetching papers...")
    papers = fetch_all_papers(config)
    print(f"  Total papers fetched: {len(papers)}")

    if not papers:
        print("\nNo papers found. Exiting.")
        return 0

    # Filter papers
    print("\n[3/5] Filtering papers...")
    filtered = filter_papers_by_embedding(papers, config.keywords)
    print(f"  Matched papers: {len(filtered)}")

    if not filtered:
        print("\nNo papers matched the filters. Exiting.")
        if not dry_run:
            # Optionally send "no papers" notification
            send_to_slack(
                [],
                token=config.slack_bot_token,
                channel=config.slack.channel,
                send_if_empty=True,
            )
        return 0

    # Print matched papers
    for i, result in enumerate(filtered, 1):
        print(f"\n  [{i}] {result.paper.title[:60]}...")
        print(f"      Reason: {result.match_reason}")

    # Summarize papers
    print("\n[4/5] Summarizing papers with Claude...")
    if dry_run and not use_bedrock and not config.anthropic_api_key:
        print("  Skipping summarization (dry run without API key)")
        # Create dummy summaries for dry run
        from .summarizer import SummarizedPaper
        summarized = [
            SummarizedPaper(
                paper=r.paper,
                summary_ja="(ドライラン: 要約は生成されません)",
                match_reason=r.match_reason,
            )
            for r in filtered
        ]
    else:
        summarized = summarize_papers(filtered, config.anthropic_api_key)
    print(f"  Summarized {len(summarized)} papers")

    # Send to Slack
    print("\n[5/5] Sending to Slack...")
    if dry_run:
        print("  [DRY RUN] Would send the following to Slack:")
        for paper in summarized:
            print(f"\n  ---")
            print(f"  Title: {paper.paper.title}")
            print(f"  URL: {paper.paper.url}")
            print(f"  Match: {paper.match_reason}")
            print(f"  Summary: {paper.summary_ja[:100]}...")
    else:
        success = send_to_slack(
            summarized,
            token=config.slack_bot_token,
            channel=config.slack.channel,
        )
        if success:
            print("  Successfully sent to Slack!")
        else:
            print("  ERROR: Failed to send to Slack")
            return 1

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch, filter, and summarize research papers"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to config YAML file",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Don't send to Slack, just print results",
    )

    args = parser.parse_args()

    sys.exit(run(config_path=args.config, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
