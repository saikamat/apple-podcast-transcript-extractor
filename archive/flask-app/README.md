# Flask Application Archive

This directory contains the archived Flask-based implementation of the podcast transcript extractor.

## Status: ARCHIVED

**Date Archived:** November 15, 2025
**Reason:** Replaced by AWS serverless architecture for production deployment

## What's Here

This directory preserves the original local Flask application that was the first implementation of this project. It includes:

- `app.py` - Main Flask web application
- `monitor_ttml.py` - Background file watcher for Apple Podcasts TTML cache
- `viewer.py` - Transcript viewer Flask app
- `clean_ttml.py` - TTML processing utility
- `templates/` - Flask HTML templates (index.html, result.html)
- `tests/` - Test scripts for OpenAI API and database capacity
- `flask-requirements.txt` - Python dependencies for Flask app

## Why Archived

The project has migrated to a fully serverless AWS architecture using:
- AWS Lambda for compute
- S3 for storage
- Step Functions for orchestration
- API Gateway for REST API
- CloudFront for CDN and frontend hosting
- DynamoDB for job tracking

The cloud architecture provides:
- Better scalability
- No server maintenance
- Pay-per-use pricing
- Global CDN distribution
- Higher availability
- No macOS dependency for TTML file access

## Running the Flask App (For Reference/Testing)

If you need to run this locally for development or testing:

### Prerequisites
- macOS with Apple Podcasts app (for auto-monitoring feature)
- Python 3.8+
- OpenAI API key

### Setup

1. Create virtual environment:
```bash
cd archive/flask-app
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r flask-requirements.txt
```

3. Create `.env` file in project root:
```bash
# In project root directory (two levels up)
echo "OPENAI_API_KEY=your_key_here" > ../../.env
```

4. Run the app:
```bash
python app.py
```

5. Access at http://127.0.0.1:5000/

### Features

- Upload TTML files via web interface
- Extract transcripts with optional timestamps
- Generate AI summaries using OpenAI GPT-3.5-turbo
- Auto-monitor Apple Podcasts cache directory (macOS only)
- View saved transcripts with `viewer.py`

### Limitations

- Requires macOS for auto-monitoring feature
- Must manually download podcast episodes in Apple Podcasts app
- Single-threaded (no concurrent processing)
- Local storage only
- No CDN or distributed access

## Production Use

For production deployments, use the AWS serverless architecture instead:
- **Live Application:** https://d35sg48h6p3ej1.cloudfront.net
- **Deployment Guide:** See `aws-cloud/DEPLOYMENT.md`
- **Architecture:** See `DEPLOYMENT_GUIDE.md` in project root

## Migration

This code was migrated to AWS Lambda functions in `aws-cloud/podcast_stack/lambda_functions/`:
- `app.py:extract_transcript()` → `lambda_functions/extract_transcript/index.py`
- `app.py:summarize_transcript()` → `lambda_functions/summarize_transcript/index.py`
- Templates replaced by CloudFront-hosted static frontend

See `MIGRATION_COMPLETE.md` in project root for full migration details.
