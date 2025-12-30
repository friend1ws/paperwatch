"""Test script for filter_embedding.py"""

import sys
sys.path.insert(0, "/Users/friend1ws/Documents/project/research_notice/workspace")

from src.fetchers.pubmed import Paper
from src.config import KeywordsConfig
from src.filter_embedding import filter_papers_by_embedding

# Create test papers
papers = [
    Paper(
        pmid="1",
        title="Long-read sequencing reveals complex structural variants in cancer genomes",
        authors=["Evan Eichler", "Glennis A. Logsdon", "John Smith"],
        abstract="We used long-read sequencing technology to analyze structural variants...",
        journal="Nature",
        pub_date="2024 Dec",
        doi="10.1038/test1",
    ),
    Paper(
        pmid="2",
        title="Pan-genome analysis of human populations",
        authors=["Bob Williams", "Alice Johnson"],
        abstract="Pangenome graphs provide a comprehensive view of genetic diversity...",
        journal="Science",
        pub_date="2024 Dec",
        doi="10.1126/test2",
    ),
    Paper(
        pmid="3",
        title="Machine learning for drug discovery",
        authors=["Jane Doe", "Mike Brown"],
        abstract="Deep learning models can predict drug-target interactions...",
        journal="Cell",
        pub_date="2024 Dec",
        doi="10.1016/test3",
    ),
    Paper(
        pmid="4",
        title="CRISPR gene editing advances",
        authors=["Glennis Logsdon", "Sarah Lee"],
        abstract="New CRISPR variants enable precise genome editing...",
        journal="Nat Biotechnol",
        pub_date="2024 Dec",
        doi="10.1038/test4",
    ),
]

# Create keywords config
keywords = KeywordsConfig(
    topics=["long-read sequencing", "pangenome", "structural variant"],
    authors=["Evan Eichler", "Glennis Logsdon"],
)

print("=" * 60)
print("Testing filter_embedding.py")
print("=" * 60)
print(f"\nTopics: {keywords.topics}")
print(f"Authors: {keywords.authors}")
print(f"\nTest papers: {len(papers)}")

print("\n" + "-" * 60)
print("Running embedding filter...")
print("-" * 60)

results = filter_papers_by_embedding(papers, keywords, similarity_threshold=0.4)

print(f"\nMatched papers: {len(results)}")

for i, result in enumerate(results, 1):
    print(f"\n[{i}] {result.paper.title}")
    print(f"    Authors: {', '.join(result.paper.authors)}")
    print(f"    Match reason: {result.match_reason}")
    print(f"    Topic scores:")
    for topic, score in result.topic_scores.items():
        marker = " ***" if score >= 0.4 else ""
        print(f"      - {topic}: {score:.3f}{marker}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
