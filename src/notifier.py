"""Slack notification module using Slack SDK."""

from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .summarizer import SummarizedPaper


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

    def _format_paper_block(self, paper: SummarizedPaper) -> list[dict]:
        """Format a paper as Slack blocks.

        Args:
            paper: SummarizedPaper to format.

        Returns:
            List of Slack block elements.
        """
        # Truncate authors list for display
        authors = paper.paper.authors[:3]
        authors_str = ", ".join(authors)
        if len(paper.paper.authors) > 3:
            authors_str += f" et al. ({len(paper.paper.authors)} authors)"

        blocks = [
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
                        "text": f"📚 {paper.paper.journal} | 👤 {authors_str}",
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
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📝 *要約:*\n{paper.summary_ja}",
                },
            },
            {"type": "divider"},
        ]

        return blocks

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

        Args:
            papers: List of summarized papers to send.
            send_if_empty: If True, send message even if no papers found.

        Returns:
            True if message was sent successfully.
        """
        if not papers and not send_if_empty:
            return True

        if not papers:
            blocks = self._create_no_papers_message()
        else:
            blocks = self._create_header_block(len(papers))
            for paper in papers:
                blocks.extend(self._format_paper_block(paper))

        # Slack has a limit of 50 blocks per message
        # If we have more, we need to split into multiple messages
        max_blocks = 50
        if len(blocks) > max_blocks:
            # Send in batches
            for i in range(0, len(blocks), max_blocks):
                batch = blocks[i : i + max_blocks]
                success = self._send_blocks(batch)
                if not success:
                    return False
            return True
        else:
            return self._send_blocks(blocks)

    def _send_blocks(self, blocks: list[dict]) -> bool:
        """Send blocks to Slack.

        Args:
            blocks: List of Slack blocks to send.

        Returns:
            True if successful.
        """
        try:
            self.client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text="論文ピックアップ",  # Fallback text for notifications
            )
            return True
        except SlackApiError as e:
            print(f"Error sending to Slack: {e.response['error']}")
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
