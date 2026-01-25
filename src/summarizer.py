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
    """Paper with English and Japanese summaries."""
    paper: Paper
    summary_en: str
    summary_ja: str
    match_reason: str


class PaperSummarizer:
    """Summarize papers using Claude API."""

    SYSTEM_PROMPT = """You are an expert in summarizing and analyzing academic papers.
For each paper, provide analysis in BOTH English and Japanese, clearly separated by the marker "---JAPANESE---".

First, write the English summary, then write "---JAPANESE---" on its own line, then write the Japanese summary.

=== ENGLISH SECTION ===

## Background
Explain the research background and motivation in 2-3 sentences. Include why this research is important and what problem it aims to solve.

## Methods
(If applicable) Briefly describe the main methods, techniques, and datasets used. Particularly important for experimental or bioinformatics research.

## Key Findings
List 3-5 main results and discoveries as bullet points. Include specific numbers and statistics if available.

## Conclusions
Summarize the research conclusions and significance in 2-3 sentences.

## Impact & Perspectives (by Claude)
This section contains Claude's analysis and insights. Discuss the following aspects in detail (10-15 sentences):

1. **Author Background**: Based on the author list, consider the characteristics and expertise of the research group. Focus on the first author, second author, second-last author, and last author, analyzing their likely research domains and how their expertise contributed to this study.

2. **Comparison with Related Work**: Discuss the relationship with other important research in this field. Analyze the novelty and advantages compared to existing methods and findings.

3. **Scientific & Social Impact**: Consider how this research might influence the academic field and society. Include significance as basic research, potential clinical applications, and contributions to technological advancement.

4. **Future Directions**: Discuss potential directions for developing this research and remaining challenges.

---JAPANESE---

=== 日本語セクション ===

## 背景
研究の背景と動機を2-3文で説明してください。なぜこの研究が重要なのか、どのような問題を解決しようとしているのかを含めてください。

## 手法
（該当する場合のみ）使用された主要な手法、技術、データセットについて簡潔に説明してください。実験的研究やバイオインフォマティクス研究の場合に特に重要です。

## 主要な発見
研究の主な結果と発見を箇条書きで3-5点挙げてください。具体的な数値や統計があれば含めてください。

## 結論
研究の結論と意義を2-3文でまとめてください。

## インパクト・展望（Claudeによる）
ここからはClaudeによる分析・考察です。以下の観点から詳細に論じてください（10-15文程度）：

1. **著者らの研究背景**: 著者リストから推測される研究グループの特徴や専門性について考察してください。特にfirst author、second author、second-last author、last authorに注目し、これらの著者らがこれまでどのような研究領域で活動してきた可能性が高いか、その専門性がこの研究にどう活かされているかを分析してください。

2. **関連研究との対比**: この研究分野における他の重要な研究との関係性を論じてください。既存の研究手法や知見と比較して、この研究がどのような新規性や優位性を持つか分析してください。

3. **科学的・社会的インパクト**: この研究が学術分野や社会にどのような影響を与える可能性があるか、詳細に考察してください。基礎研究としての意義、臨床応用の可能性、技術発展への貢献などを含めてください。

4. **今後の展望**: この研究を発展させる可能性のある方向性や、残された課題について論じてください。

専門用語は適切に日本語に訳すか、英語のまま残してください。"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize summarizer.

        Args:
            api_key: Anthropic API key (not needed for Bedrock).
            model: Model to use for summarization. If None, uses default for backend.
        """
        self.client, default_model = create_client(api_key)
        self.model = model or default_model

    def summarize_paper(self, paper: Paper) -> tuple[str, str]:
        """Summarize a single paper.

        Args:
            paper: Paper to summarize.

        Returns:
            Tuple of (English summary, Japanese summary).
        """
        user_prompt = f"""Please summarize the following paper in both English and Japanese.

Title: {paper.title}

Authors: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}

Journal: {paper.journal}

Abstract:
{paper.abstract}"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=5000,
            system=self.SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        full_response = message.content[0].text

        # Split response into English and Japanese parts
        if "---JAPANESE---" in full_response:
            parts = full_response.split("---JAPANESE---", 1)
            summary_en = parts[0].strip()
            summary_ja = parts[1].strip()
        else:
            # Fallback if marker not found
            summary_en = full_response
            summary_ja = "(日本語要約の生成に失敗しました)"

        return summary_en, summary_ja

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
                summary_en, summary_ja = self.summarize_paper(result.paper)
                summarized.append(
                    SummarizedPaper(
                        paper=result.paper,
                        summary_en=summary_en,
                        summary_ja=summary_ja,
                        match_reason=result.match_reason,
                    )
                )
            except Exception as e:
                print(f"Error summarizing paper {result.paper.pmid}: {e}")
                # Include paper without summary
                summarized.append(
                    SummarizedPaper(
                        paper=result.paper,
                        summary_en="(Failed to generate summary)",
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
