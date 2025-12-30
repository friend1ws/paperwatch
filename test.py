from src.fetchers import BioRxivFetcher
from collections import Counter

print('=== bioRxiv categories (5 days) ===')
with BioRxivFetcher() as fetcher:
    papers = fetcher.fetch_papers(server='biorxiv', days_back=5)
    
    # Extract categories
    categories = []
    for p in papers:
        # journal format: 'biorxiv (category)'
        if '(' in p.journal:
            cat = p.journal.split('(')[1].rstrip(')')
            categories.append(cat)
    
    # Count
    counter = Counter(categories)
    print(f'Total papers: {len(papers)}')
    print(f'\\nTop categories:')
    for cat, count in counter.most_common(20):
        print(f'  {cat}: {count}')

