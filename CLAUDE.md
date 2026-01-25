# CLAUDE.md

This file provides guidance for Claude Code when working with this repository.

## Local Analysis Setup

When running analysis locally, the following setup is required:

### 1. Environment Variables

Currently using AWS Bedrock for Claude API access. Set the following environment variable:

```bash
export USE_BEDROCK=1
```

### 2. AWS Configuration

Ensure AWS CLI is properly configured:

```bash
aws configure
```

Your AWS credentials (Access Key ID, Secret Access Key) and region must be set.

### 3. Activate Python Virtual Environment

Activate the virtual environment to use the required Python packages:

```bash
source .venv/bin/activate
```

### Example Usage

```bash
# Set environment variable
export USE_BEDROCK=1

# Activate virtual environment
source .venv/bin/activate

# Dry run (no Slack notification)
python -m src.main --dry-run

# Production run
python -m src.main
```
