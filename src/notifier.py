"""Slack notification module using Slack SDK."""

import time
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .summarizer import SummarizedPaper


SLACK_SECTION_TEXT_LIMIT = 2800


def _split_markdown_text(
    text: str,
    prefix: str,
    limit: int = SLACK_SECTION_TEXT_LIMIT,
) -> list[str]:
    """Split Markdown text into Slack section-sized chunks."""
    if len(prefix) + len(text) <= limit:
        return [f"{prefix}{text}"]

    chunks = []
    current = prefix
    for paragraph in text.split("\n\n"):
        addition = f"{paragraph}\n\n"
        while addition:
            remaining = limit - len(current)
            if len(addition) <= remaining:
                current += addition
                break

            if remaining > 0:
                current += addition[:remaining]
                addition = addition[remaining:]

            if current.strip():
                chunks.append(current.rstrip())
            current = ""

    if current.strip():
        chunks.append(current.rstrip())

    return chunks


class SlackNotifier:
    """Send paper notifications to Slack."""

    def __init__(self, token: str, channel: str = "#research-papers"):
        """Initialize Slack notifier.

        Args:
            token: Slack Bot Token (xoxb-...).
            channel: Channel to post to.
        """
        self.client = WebClient(token=token)
        self.channel = channel

    def _format_paper_blocks(self, paper: SummarizedPaper) -> tuple[list[dict], list[dict]]:
        """Format a paper as two sets of Slack blocks (EN and JA).

        Args:
            paper: SummarizedPaper to format.

        Returns:
            Tuple of (English blocks, Japanese blocks).
        """
        # Truncate authors list for display
        authors = paper.paper.authors[:3]
        authors_str = ", ".join(authors)
        if len(paper.paper.authors) > 3:
            authors_str += f" et al. ({len(paper.paper.authors)} authors)"

        # English summary blocks (includes paper metadata)
        blocks_en = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{paper.paper.url}|{paper.paper.title}>*",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"📚 {paper.paper.journal} | 👤 {authors_str} | "
                            f"Source: {paper.summary_source}"
                        ),
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔍 *マッチ理由:* {paper.match_reason}",
                },
            },
        ]
        blocks_en.extend(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": chunk},
            }
            for chunk in _split_markdown_text(
                paper.summary_en,
                "📝 *Summary (EN):*\n",
            )
        )

        # Japanese summary blocks
        blocks_ja = [
            *(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": chunk},
                }
                for chunk in _split_markdown_text(
                    paper.summary_ja,
                    "📝 *要約 (JA):*\n",
                )
            ),
            {
                "type": "divider",
            },
        ]

        return blocks_en, blocks_ja

    def _create_header_block(self, paper_count: int) -> list[dict]:
        """Create header block for the notification.

        Args:
            paper_count: Number of papers being reported.

        Returns:
            List of Slack block elements for header.
        """
        today = datetime.now().strftime("%Y年%m月%d日")
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📖 本日の論文ピックアップ ({today})",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"関連する論文が *{paper_count}件* 見つかりました。",
                },
            },
            {"type": "divider"},
        ]

    def _create_no_papers_message(self) -> list[dict]:
        """Create message for when no papers are found.

        Returns:
            List of Slack block elements.
        """
        today = datetime.now().strftime("%Y年%m月%d日")
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📖 本日の論文ピックアップ ({today})",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "本日は関連する新着論文がありませんでした。",
                },
            },
        ]

    def send_papers(
        self,
        papers: list[SummarizedPaper],
        send_if_empty: bool = False,
    ) -> bool:
        """Send papers to Slack.

        Each paper is sent as a separate message to avoid Slack's text limits.

        Args:
            papers: List of summarized papers to send.
            send_if_empty: If True, send message even if no papers found.

        Returns:
            True if all messages were sent successfully.
        """
        if not papers and not send_if_empty:
            return True

        if not papers:
            blocks = self._create_no_papers_message()
            return self._send_blocks(blocks)

        # Send header message first
        header_blocks = self._create_header_block(len(papers))
        if not self._send_blocks(header_blocks):
            return False

        # Send each paper as separate messages (EN and JA) to avoid text length limits
        for paper in papers:
            blocks_en, blocks_ja = self._format_paper_blocks(paper)
            if not self._send_blocks(blocks_en):
                return False
            if not self._send_blocks(blocks_ja):
                return False

        return True

    def _send_blocks(self, blocks: list[dict], max_retries: int = 3) -> bool:
        """Send blocks to Slack with rate limit handling.

        Args:
            blocks: List of Slack blocks to send.
            max_retries: Maximum number of retries for rate limiting.

        Returns:
            True if successful.
        """
        for attempt in range(max_retries):
            try:
                self.client.chat_postMessage(
                    channel=self.channel,
                    blocks=blocks,
                    text="論文ピックアップ",  # Fallback text for notifications
                )
                # Add delay between messages to avoid rate limiting
                time.sleep(1.5)
                return True
            except SlackApiError as e:
                error = e.response['error']
                if error == 'ratelimited':
                    # Get retry-after header, default to 5 seconds
                    retry_after = int(e.response.headers.get('Retry-After', 5))
                    print(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                else:
                    print(f"Error sending to Slack: {error}")
                    return False
        print("Max retries exceeded for rate limiting")
        return False


def send_to_slack(
    papers: list[SummarizedPaper],
    token: str,
    channel: str = "#research-papers",
    send_if_empty: bool = False,
) -> bool:
    """Convenience function to send papers to Slack.

    Args:
        papers: List of summarized papers.
        token: Slack Bot Token.
        channel: Channel to post to.
        send_if_empty: If True, send message even if no papers.

    Returns:
        True if successful.
    """
    notifier = SlackNotifier(token=token, channel=channel)
    return notifier.send_papers(papers, send_if_empty)
