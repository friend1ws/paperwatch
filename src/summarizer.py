"""Paper summarizer using Claude API."""

import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from .fetchers.pubmed import Paper
from .filter import FilterResult


# Default models for each backend
DEFAULT_MODEL_DIRECT = "claude-opus-4-5-20251101"
DEFAULT_MODEL_BEDROCK = "global.anthropic.claude-opus-4-5-20251101-v1:0"


def create_client(api_key: Optional[str] = None) -> tuple[anthropic.Anthropic, str]:
    """Create appropriate Anthropic client based on environment.

    Args:
        api_key: Anthropic API key (used only for direct API).

    Returns:
        Tuple of (client, default_model).
    """
    use_bedrock = os.environ.get("USE_BEDROCK", "").lower() in ("1", "true", "yes")

    if use_bedrock:
        return anthropic.AnthropicBedrock(), DEFAULT_MODEL_BEDROCK
    else:
        return anthropic.Anthropic(api_key=api_key), DEFAULT_MODEL_DIRECT


@dataclass
class SummarizedPaper:
    """Paper with Japanese summary."""
    paper: Paper
    summary_ja: str
    match_reason: str


class PaperSummarizer:
    """Summarize papers using Claude API."""

    SYSTEM_PROMPT = """あなたは学術論文の要約を行う専門家です。
与えられた論文のアブストラクトを日本語で簡潔に要約してください。

要約のルール:
1. 3-5文で要約する
2. 研究の目的、手法、主要な発見を含める
3. 専門用語は適切に日本語に訳すか、英語のまま残す
4. 箇条書きは使わず、流れのある文章で書く"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize summarizer.

        Args:
            api_key: Anthropic API key (not needed for Bedrock).
            model: Model to use for summarization. If None, uses default for backend.
        """
        self.client, default_model = create_client(api_key)
        self.model = model or default_model

    def summarize_paper(self, paper: Paper) -> str:
        """Summarize a single paper.

        Args:
            paper: Paper to summarize.

        Returns:
            Japanese summary of the paper.
        """
        user_prompt = f"""以下の論文を日本語で要約してください。

タイトル: {paper.title}

著者: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}

ジャーナル: {paper.journal}

アブストラクト:
{paper.abstract}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        return message.content[0].text

    def summarize_papers(
        self,
        filter_results: list[FilterResult],
    ) -> list[SummarizedPaper]:
        """Summarize multiple papers.

        Args:
            filter_results: List of filtered papers to summarize.

        Returns:
            List of SummarizedPaper objects.
        """
        summarized = []

        for result in filter_results:
            try:
                summary = self.summarize_paper(result.paper)
                summarized.append(
                    SummarizedPaper(
                        paper=result.paper,
                        summary_ja=summary,
                        match_reason=result.match_reason,
                    )
                )
            except Exception as e:
                print(f"Error summarizing paper {result.paper.pmid}: {e}")
                # Include paper without summary
                summarized.append(
                    SummarizedPaper(
                        paper=result.paper,
                        summary_ja="(要約の生成に失敗しました)",
                        match_reason=result.match_reason,
                    )
                )

        return summarized


def summarize_papers(
    filter_results: list[FilterResult],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> list[SummarizedPaper]:
    """Convenience function to summarize papers.

    Args:
        filter_results: List of filtered papers.
        api_key: Anthropic API key (not needed for Bedrock).
        model: Model to use. If None, uses default for backend.

    Returns:
        List of SummarizedPaper objects.
    """
    summarizer = PaperSummarizer(api_key=api_key, model=model)
    return summarizer.summarize_papers(filter_results)
