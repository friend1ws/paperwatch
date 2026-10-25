"""Paper summarizer using Claude API."""

import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from .fetchers.pubmed import Paper
from .filter import FilterResult


# Default models for each backend
DEFAULT_MODEL_DIRECT = "claude-opus-5-5"
DEFAULT_MODEL_BEDROCK = "global.anthropic.claude-opus-5-5"  # inference profile required

# Fallback models used when the default model declines (stop_reason == "refusal")
FALLBACK_MODEL_DIRECT = "claude-opus-4-8"
FALLBACK_MODEL_BEDROCK = "global.anthropic.claude-opus-4-8"


def get_default_model() -> str:
    """Return the default model for the configured backend."""
    use_bedrock = os.environ.get("USE_BEDROCK", "").lower() in ("1", "true", "yes")
    return DEFAULT_MODEL_BEDROCK if use_bedrock else DEFAULT_MODEL_DIRECT


def get_fallback_model() -> str:
    """Return the refusal fallback model for the configured backend."""
    use_bedrock = os.environ.get("USE_BEDROCK", "").lower() in ("1", "true", "yes")
    return FALLBACK_MODEL_BEDROCK if use_bedrock else FALLBACK_MODEL_DIRECT


def create_client(api_key: Optional[str] = None) -> tuple[anthropic.Anthropic, str]:
    """Create appropriate Anthropic client based on environment.

    Args:
        api_key: Anthropic API key (used only for direct API).

    Returns:
        Tuple of (client, default_model).
    """
    use_bedrock = os.environ.get("USE_BEDROCK", "").lower() in ("1", "true", "yes")

    if use_bedrock:
        return anthropic.AnthropicBedrock(), get_default_model()
    else:
        return anthropic.Anthropic(api_key=api_key), get_default_model()


@dataclass
class SummarizedPaper:
    """Paper with English and Japanese summaries."""
    paper: Paper
    summary_en: str
    summary_ja: str
    match_reason: str
    summary_source: str = "abstract"


class PaperSummarizer:
    """Summarize papers using Claude API."""

    SYSTEM_PROMPT = """You are an expert in summarizing and analyzing academic papers.
For each paper, provide analysis in BOTH English and Japanese, clearly separated by the marker "---JAPANESE---".

IMPORTANT: Each section (English and Japanese) MUST be within 2800 characters to fit Slack's message limits. Be concise.

First, write the English summary, then write "---JAPANESE---" on its own line, then write the Japanese summary.

=== ENGLISH SECTION (max 2800 characters) ===

## Background
Explain the research background and motivation in 2-3 sentences. Include why this research is important and what problem it aims to solve.

## Methods
(If applicable) Briefly describe the main methods, techniques, and datasets used. Particularly important for experimental or bioinformatics research.

## Key Findings
List 3-5 main results and discoveries as bullet points. Include specific numbers and statistics if available.

## Conclusions
Summarize the research conclusions and significance.

## Impact & Perspectives (by Claude)
Claude's brief analysis:
- Novelty compared to related work
- Scientific/social impact potential
- Future directions

---JAPANESE---

=== 日本語セクション (最大2800文字) ===

## 背景
研究の背景と動機を2-3文で説明してください。なぜこの研究が重要なのか、どのような問題を解決しようとしているのかを含めてください。

## 手法
（該当する場合のみ）使用された主要な手法、技術、データセットについて簡潔に説明してください。実験的研究やバイオインフォマティクス研究の場合に特に重要です。

## 主要な発見
研究の主な結果と発見を箇条書きで3-5点挙げてください。具体的な数値や統計があれば含めてください。

## 結論
研究の結論と意義をまとめてください。

## インパクト・展望（Claudeによる）
Claudeによる簡潔な分析：
- 関連研究と比較した新規性
- 科学的・社会的インパクトの可能性
- 今後の展望

専門用語は適切に日本語に訳すか、英語のまま残してください。"""

    FULL_TEXT_SYSTEM_PROMPT = """You are an expert scientific reviewer reading extracted full text from an academic paper.
For each paper, provide analysis in BOTH English and Japanese, clearly separated by the marker "---JAPANESE---".

IMPORTANT: The full-text review should be substantially more detailed than an abstract summary. Aim for about 8000 characters total across English and Japanese, with a short English section and a much more detailed Japanese section. Be evidence-focused and do not invent details not present in the provided text.

The input may come from PDF text extraction and may be noisy or truncated. Prefer concrete claims supported by the text. If the full text excerpt is truncated or a detail is missing, do not pretend it was available.

First, write the English review, then write "---JAPANESE---" on its own line, then write the Japanese review.

=== ENGLISH SECTION (about 1200-1600 characters) ===

## Bottom Line
State the main contribution and why it matters in 2-3 sentences.

## Evidence Snapshot
Summarize the study design, datasets, experiments, and 3-5 key results. Include important numbers when available.

## Assessment
Briefly explain what is interesting, likely impact, main caveats, and if this is a bioRxiv/medRxiv preprint, what journal tier it might plausibly fit and why.

---JAPANESE---

=== 日本語セクション (約6000-7000文字) ===

## 1. この論文の要点
この論文が何を主張しているのか、何が新しいのか、なぜ読む価値があるのかを最初に明確に書いてください。

## 2. 何をした論文か
研究デザイン、データ、実験、計算手法、コホート、サンプル、ベンチマーク、比較対象を具体的に説明してください。本文にある重要な数値、条件、データ規模、検証方法があれば必ず含めてください。

## 3. どこが面白いか
この論文の科学的に面白い点、技術的にうまい点、発想の良い点、既存研究との差分を深掘りしてください。単なる宣伝ではなく、本文中の結果や設計に基づいて評価してください。

## 4. 主要な結果と根拠
本文に基づく主要な結果を、具体的な根拠とともに整理してください。効果量、性能差、統計値、図表で示された結果、再現性検証、外部データでの確認などがあれば優先してください。

## 5. どのくらいインパクトがありそうか
分野内での重要度、応用可能性、後続研究への波及、既存の見方を変える可能性を評価してください。インパクトを「高い・中程度・限定的」などで明示し、その理由を本文に基づいて説明してください。

## 6. bioRxiv/medRxivの場合、どのくらいのジャーナルに通りそうか
この入力がbioRxiv/medRxiv由来のpreprintである場合、本文から見える完成度、データ量、検証の厚み、新規性、ストーリーの強さ、限界を踏まえて、どの程度のジャーナル帯に通りそうかを推定してください。例: top-tier general journal, high-impact field journal, solid specialist journal, methods/resource journal, additional validation needed など。断定せず、理由と条件付きで書いてください。bioRxiv/medRxivでない場合は、この項目は短く「該当なし」としてください。

## 7. 弱点・注意点
本文から読み取れる限界、仮定、欠けている対照、データ制約、解釈上のリスク、査読で突かれそうな点を具体的に書いてください。

## 8. 自分なら次に何を見るか
この論文を本当に信じるために追加で見たい解析・実験・データ、また次に追うべき研究展開を挙げてください。

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
        source_label = paper.full_text_source if paper.full_text else "abstract"
        source_heading = "Full text excerpt" if paper.full_text else "Abstract"
        source_text = paper.full_text if paper.full_text else paper.abstract
        system_prompt = self.FULL_TEXT_SYSTEM_PROMPT if paper.full_text else self.SYSTEM_PROMPT

        task_intro = (
            "Please review the following paper using the extracted full text."
            if paper.full_text
            else "Please summarize the following paper in both English and Japanese."
        )

        user_prompt = f"""{task_intro}

Title: {paper.title}

Authors: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}

Journal: {paper.journal}

Summary source: {source_label}

{source_heading}:
{source_text}"""

        # Opus 5.5 always thinks, and thinking tokens count toward max_tokens
        max_tokens = 24000 if paper.full_text else 16000

        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            # Opus 5.5 defaults to "medium"; set explicitly
            extra_body={"output_config": {"effort": "medium"}},
        )

        if message.stop_reason == "refusal":
            # Safety classifiers (e.g. "bio") may decline; retry on the previous model
            fallback_model = get_fallback_model()
            print(f"  Refused by {self.model}; retrying with {fallback_model}")
            message = self.client.messages.create(
                model=fallback_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )

        # Response may start with a thinking block; collect text blocks only
        full_response = "".join(
            block.text for block in message.content if block.type == "text"
        )

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
                        summary_source=result.paper.full_text_source or "abstract",
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
                        summary_source=result.paper.full_text_source or "abstract",
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
