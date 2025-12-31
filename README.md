# Paperwatch

A tool to automatically fetch, filter, summarize, and notify about new research papers from PubMed and bioRxiv/medRxiv.

## Features

- **Fetch papers** from PubMed and bioRxiv/medRxiv
- **Filter papers** by:
  - Topic keywords (using semantic similarity with sentence embeddings)
  - Author names (with intelligent name matching)
- **Summarize** matched papers in Japanese using Claude API
- **Notify** via Slack

## Requirements

- Python 3.11+
- AWS credentials (for Bedrock) or Anthropic API key
- Slack Bot Token

## Installation

```bash
# Clone the repository
git clone https://github.com/friend1ws/paperwatch.git
cd paperwatch

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Edit config file

Edit `config/config.yaml`:

```yaml
journals:
  pubmed:
    - Nature
    - Science
    - Cell
    # Add more journals...
  preprint:
    - bioRxiv
    - medRxiv
  preprint_categories:
    biorxiv:
      - bioinformatics
      - genomics
      - genetics
    medrxiv:
      - genetic and genomic medicine

keywords:
  topics:
    - long-read
    - pangenome
    - structural variation
    # Add your topics...
  authors:
    - Evan Eichler
    - Heng Li
    # Add authors to track...

search:
  days_back: 1  # Number of days to search (1 = yesterday only)

slack:
  # Use channel ID instead of channel name (e.g., "C01234ABCDE")
  channel: "YOUR_CHANNEL_ID"

schedule:
  time: "09:00"
  timezone: "Asia/Tokyo"
```

### 2. Set environment variables

```bash
# For AWS Bedrock (recommended)
export USE_BEDROCK=1
# AWS credentials should be configured via ~/.aws/credentials or environment variables

# OR for direct Anthropic API
export ANTHROPIC_API_KEY=your_api_key

# Slack Bot Token (required)
export SLACK_BOT_TOKEN=xoxb-your-token
```

## Usage

### Run the full pipeline

```bash
# Using config file
python -m src.main --config config/config.yaml

# Dry run (no Slack notification)
python -m src.main --config config/config.yaml --dry-run
```

### Command-line options

```
usage: python -m src.main [-h] [--config CONFIG] [--dry-run]

Fetch, filter, and summarize research papers

options:
  -h, --help            show this help message and exit
  --config, -c CONFIG   Path to config YAML file
  --dry-run, -n         Don't send to Slack, just print results
```

### Example output

```
============================================================
Research Paper Notification - 2025-12-31 09:00
============================================================

[1/5] Loading configuration...
  Using AWS Bedrock
  Topics: long-read, pangenome, structural variation, ...
  Authors: Evan Eichler, Heng Li, ...
  Days back: 1

[2/5] Fetching papers...
Fetching papers from PubMed (14 journals)...
  Found 25 papers from PubMed
Fetching preprints (bioRxiv, medRxiv)...
  Found 30 preprints
  Total papers fetched: 55

[3/5] Filtering papers...
  Loading embedding model: all-MiniLM-L6-v2...
  Matched papers: 2

  [1] New long-read sequencing method reveals...
      Reason: Authors: Evan Eichler; Topics: long-read (0.52)

[4/5] Summarizing papers with Claude...
  Summarized 2 papers

[5/5] Sending to Slack...
  Successfully sent to Slack!

============================================================
Done!
============================================================
```

## Project Structure

```
paperwatch/
├── .github/
│   └── workflows/
│       └── daily_papers.yaml  # GitHub Actions workflow
├── config/
│   └── config.yaml            # Configuration file (gitignored)
├── src/
│   ├── __init__.py
│   ├── main.py                # Main entry point
│   ├── config.py              # Configuration loader
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── pubmed.py          # PubMed fetcher
│   │   └── biorxiv.py         # bioRxiv/medRxiv fetcher
│   ├── filter_embedding.py    # Paper filtering with embeddings
│   ├── summarizer.py          # Claude summarization
│   └── notifier.py            # Slack notification
├── requirements.txt
├── pyproject.toml
└── README.md
```

## How It Works

### Date Range

With `days_back: 1`, the system searches for papers published **yesterday only** (not including today). This prevents duplicate notifications when running daily.

- Run on 2025-01-01 → searches papers from 2024-12-31
- Run on 2025-01-02 → searches papers from 2025-01-01

### Topic Matching

Uses sentence embeddings (all-MiniLM-L6-v2) to calculate semantic similarity between paper abstracts and topic keywords. Papers with similarity score >= 0.4 are matched.

### Author Matching

Handles various name formats:
- "Firstname Lastname" (PubMed format)
- "Lastname, Firstname" (bioRxiv format)
- Matches initials (e.g., "E. Eichler" matches "Evan Eichler")

## Slack Setup

1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes:
   - `chat:write`
   - `chat:write.public` (for public channels)
3. Install the app to your workspace
4. Copy the Bot User OAuth Token (`xoxb-...`)
5. Invite the bot to your target channel

## Scheduled Execution

For daily notifications, set up a cron job or scheduled task:

```bash
# Example crontab entry (run at 9:00 AM JST daily)
0 9 * * * cd /path/to/workspace && USE_BEDROCK=1 SLACK_BOT_TOKEN=xoxb-xxx /path/to/venv/bin/python -m src.main -c config/config.yaml
```

## GitHub Actions Setup

You can run this tool automatically using GitHub Actions.

### 1. Fork or clone this repository

### 2. Set up GitHub Secrets

Go to your repository's **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add the following secrets:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `CONFIG_YAML` | Contents of your `config/config.yaml` file | ✓ |
| `USE_BEDROCK` | Set to `1` to use AWS Bedrock | ✓ |
| `AWS_ACCESS_KEY_ID` | AWS Access Key ID | ✓ |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Access Key | ✓ |
| `AWS_REGION` | AWS Region (e.g., `us-east-1`) | ✓ |
| `SLACK_BOT_TOKEN` | Slack Bot Token (`xoxb-...`) | ✓ |
| `PUBMED_API_KEY` | PubMed API Key (increases rate limit) | Optional |

### 3. CONFIG_YAML Secret

Copy the entire contents of your `config/config.yaml` file and paste it as the value for the `CONFIG_YAML` secret. You can paste the YAML as-is (no encoding needed).

Example:
```yaml
journals:
  pubmed:
    - Nature
    - Science
  preprint:
    - bioRxiv

keywords:
  topics:
    - long-read
    - pangenome
  authors:
    - Evan Eichler

search:
  days_back: 1

slack:
  # Use channel ID instead of channel name (e.g., "C01234ABCDE")
  channel: "YOUR_CHANNEL_ID"

schedule:
  time: "09:00"
  timezone: "Asia/Tokyo"
```

### 4. Run the workflow

The workflow runs automatically at 9:00 AM JST (0:00 UTC) daily.

To run manually:
1. Go to **Actions** tab
2. Select **Daily Paper Notification**
3. Click **Run workflow**

## License

MIT
