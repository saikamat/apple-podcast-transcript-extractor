# AWS Cloud Deployment - Podcast Transcript Summarizer

This directory contains the Infrastructure as Code (IaC) for deploying the podcast transcript summarizer to AWS.

## Architecture

- **S3**: Storage for TTML files, transcripts, and summaries
- **DynamoDB**: Job tracking and metadata
- **Lambda**: Extract transcript and summarize functions
- **Step Functions**: Orchestrates processing workflow
- **API Gateway**: REST API for upload and result retrieval
- **Secrets Manager**: Stores OpenAI API key

## Setup

1. Install dependencies:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

3. Configure AWS credentials:
```bash
aws configure
```

4. Set up secrets (dev):
```bash
aws secretsmanager create-secret \
  --name podcast-app/openai-key-dev \
  --secret-string "your-openai-api-key-here" \
  --region us-east-1
```

5. Deploy dev environment:
```bash
cdk deploy PodcastStackStack-dev
```

6. Deploy prod environment:
```bash
cdk deploy PodcastStackStack-prod
```

## Directory Structure

```
podcast_stack/
├── app.py                          # CDK app entry point
├── podcast_stack/
│   ├── __init__.py
│   └── podcast_stack_stack.py      # Main stack definition
├── lambda_functions/               # Lambda function code
│   ├── extract_transcript/
│   ├── summarize_transcript/
│   ├── presign/
│   └── get_result/
└── requirements.txt
```

