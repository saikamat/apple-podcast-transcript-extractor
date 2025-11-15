# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A cloud-native serverless podcast transcript extractor and summarizer that processes Apple Podcasts TTML files.

**Production Architecture**: AWS serverless (Lambda, S3, Step Functions, API Gateway, CloudFront)
**Live URL**: https://d35sg48h6p3ej1.cloudfront.net
**API Endpoint**: https://g5oco2erb4.execute-api.us-east-1.amazonaws.com/prod/

**Archived**: Original Flask local application moved to `archive/flask-app/` (kept for reference only)

## Core Architecture

### AWS Cloud Architecture (Production)

**Directory**: `aws-cloud/podcast_stack/`
**Status**: Production deployment, 100% serverless

Serverless event-driven pipeline:
1. Frontend requests presigned S3 URL from API Gateway
2. File uploads directly to S3 `uploads/` prefix
3. S3 event triggers `start_pipeline` Lambda
4. Step Functions orchestrates: Extract Lambda → Summarize Lambda
5. Results stored in S3 (`transcripts/`, `summaries/`)
6. Job status tracked in DynamoDB

**CDK Stack**: `podcast_stack/podcast_stack_stack.py`
- Single production environment with production-grade configurations
- S3 lifecycles: 30/90/180 days for uploads/transcripts/summaries
- Lambda memory: 512MB (extract), 1024MB (summarize), 256MB (API handlers)
- Removal policy: RETAIN (data preserved on stack deletion)

**Lambda Functions**:
- `lambda_functions/presign/` - Generates S3 presigned PUT URLs, creates DynamoDB job records
- `lambda_functions/start_pipeline/` - Triggered by S3 uploads, starts Step Functions execution
- `lambda_functions/extract_transcript/` - Parses TTML XML, reads from S3, writes to S3/DynamoDB
- `lambda_functions/summarize_transcript/` - Calls OpenAI API with rate limiting, writes to S3/DynamoDB
- `lambda_functions/get_result/` - Queries DynamoDB, returns presigned GET URLs for results

**Frontend**: Static HTML/JavaScript (`index.html` in project root)
- Hosted on S3 bucket
- Distributed via CloudFront CDN
- Direct S3 uploads using presigned URLs
- Real-time status polling

## Development Commands

### AWS Cloud Deployment (Primary)

**Setup**:
```bash
cd aws-cloud/podcast_stack
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Store secrets** (first time):
```bash
aws secretsmanager create-secret \
  --name podcast-app/openai-key-prod \
  --secret-string '{"OPENAI_API_KEY":"your-key"}'
```

**Bootstrap CDK** (first time per account/region):
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

**Deploy production**:
```bash
cd aws-cloud/podcast_stack
cdk deploy PodcastStackStack-prod
```

**View changes before deploying**:
```bash
cdk diff PodcastStackStack-prod
```

**Synthesize CloudFormation template**:
```bash
cdk synth
```

**Destroy (with manual cleanup required)**:
```bash
cdk destroy PodcastStackStack-prod
# Note: S3 buckets and DynamoDB tables are retained for safety
# Delete them manually if needed
```

**Update frontend**:
```bash
# Edit index.html in project root
# Upload to S3 via AWS console or CLI
aws s3 cp index.html s3://BUCKET_NAME/index.html
# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/*"
```

## Key Technical Details

### TTML Parsing
- Uses `xml.etree.ElementTree` with namespace `http://www.w3.org/ns/ttml`
- Searches for `<p>` elements, extracts text from nested `<span>` elements
- Optional timestamps from `begin` attribute (formatted as HH:MM:SS)

### OpenAI Rate Limiting Strategy
Lambda implementations use:
- 4000-character chunks
- 3-second delays between initial requests
- Exponential backoff: `min(60, 2^retry_count)` seconds
- Max 8 retries per chunk
- Fallback placeholder text on exhaustion

### AWS Infrastructure Patterns
- IAM roles use least-privilege (separate role for starter Lambda to avoid circular refs)
- S3 lifecycle rules auto-delete files by prefix
- DynamoDB uses PAY_PER_REQUEST billing (no provisioned capacity)
- CORS enabled on S3 and API Gateway for browser uploads
- Step Functions timeout: 15 minutes
- Presigned URLs for upload (PUT) and download (GET)

## Important Files

**AWS serverless (production)**:
- `aws-cloud/DEPLOYMENT.md` - Step-by-step AWS deployment guide
- `aws-cloud/MIGRATION_SUMMARY.md` - Architecture comparison and migration details
- `aws-cloud/podcast_stack/app.py` - CDK app entry point (defines production stack)
- `aws-cloud/podcast_stack/podcast_stack/podcast_stack_stack.py` - Infrastructure definition (S3, Lambda, Step Functions, DynamoDB, API Gateway, CloudFront)
- `aws-cloud/podcast_stack/lambda_functions/*/index.py` - Lambda function implementations
- `index.html` - CloudFront-hosted frontend (project root)
- `aws-test.html` - Testing utility for upload pipeline

**Documentation**:
- `README.md` - Main project documentation (cloud-first)
- `DEPLOYMENT_GUIDE.md` - Complete AWS deployment instructions
- `MIGRATION_COMPLETE.md` - Migration summary and history
- `CLAUDE.md` - This file

**Archived (reference only)**:
- `archive/flask-app/` - Original Flask implementation (not for production)
- `archive/flask-app/README.md` - Flask app documentation

## Environment Variables

### AWS Lambda
- `STORAGE_BUCKET` - S3 bucket name (set by CDK)
- `JOB_TABLE` - DynamoDB table name (set by CDK)
- `SECRET_NAME` - Secrets Manager secret name (set by CDK)
- `STATE_MACHINE_ARN` - Step Functions ARN (set by CDK, starter Lambda only)
- `BUCKET_NAME` - Duplicate of STORAGE_BUCKET (starter Lambda only)

### Local Development (Archived)
- `.env` file no longer used for production
- See `archive/flask-app/README.md` for Flask-specific env setup

## Testing

### AWS Cloud (Production)
See aws-cloud/DEPLOYMENT.md "Testing" section for presigned URL workflow and API endpoint testing with curl.

**Quick test**:
1. Open https://d35sg48h6p3ej1.cloudfront.net
2. Upload a TTML file
3. Monitor Step Functions execution in AWS console
4. Check CloudWatch logs for debugging

**API testing**:
```bash
# Get presigned URL
curl -X POST https://g5oco2erb4.execute-api.us-east-1.amazonaws.com/prod/presign \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.ttml"}'

# Check job status
curl "https://g5oco2erb4.execute-api.us-east-1.amazonaws.com/prod/result?jobId=YOUR_JOB_ID"
```

**Browser testing**:
Open `aws-test.html` in browser to test full pipeline.

## Project Directory Structure

```
.
├── README.md                     # Main documentation (cloud-first)
├── DEPLOYMENT_GUIDE.md           # AWS deployment instructions
├── MIGRATION_COMPLETE.md         # Migration summary
├── CLAUDE.md                     # This file
├── index.html                    # CloudFront-hosted frontend
├── aws-test.html                 # Testing utility
├── env.example                   # Environment template
├── requirements.txt              # Minimal AWS CLI/CDK requirements
├── .gitignore                    # Git ignore rules
├── archive/                      # Archived Flask implementation
│   └── flask-app/                # Original local application
│       ├── README.md             # Flask documentation
│       ├── app.py                # Main Flask app
│       ├── monitor_ttml.py       # TTML file watcher
│       ├── viewer.py             # Transcript viewer
│       ├── clean_ttml.py         # TTML utility
│       ├── templates/            # Flask HTML templates
│       ├── tests/                # Test scripts
│       └── flask-requirements.txt # Flask dependencies
└── aws-cloud/                    # AWS serverless (production)
    ├── DEPLOYMENT.md             # Deployment guide
    ├── MIGRATION_SUMMARY.md      # Architecture comparison
    └── podcast_stack/            # CDK project
        ├── app.py                # CDK entry point
        ├── requirements.txt      # CDK dependencies
        ├── lambda_functions/     # Lambda source code
        │   ├── presign/
        │   ├── start_pipeline/
        │   ├── extract_transcript/
        │   ├── summarize_transcript/
        │   └── get_result/
        └── podcast_stack/        # CDK stack definitions
            └── podcast_stack_stack.py
```

## AWS Lambda Deployment - Critical Configuration

**IMPORTANT**: Lambda functions require proper dependency bundling and architecture configuration.

### Requirements for each Lambda function:
1. **requirements.txt** - Must exist in each lambda_functions/*/  directory
2. **Architecture specification** - `architecture=_lambda.Architecture.X86_64` in CDK stack
3. **Platform specification** - `platform="linux/amd64"` in bundling options
4. **Docker** - Must be running for CDK bundling to work

### Common Lambda deployment errors:
- `Runtime.ImportModuleError: No module named 'openai'` → Missing requirements.txt or bundling not configured
- `No module named 'pydantic_core._pydantic_core'` → Architecture mismatch (ARM64 vs x86_64)

### CDK Bundling Configuration:
All Lambda functions in `podcast_stack_stack.py` use:
```python
code=_lambda.Code.from_asset(
    "lambda_functions/function_name",
    bundling=cdk.BundlingOptions(
        image=_lambda.Runtime.PYTHON_3_12.bundling_image,
        command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"],
        platform="linux/amd64"  # Critical for x86_64 Lambda runtime
    )
)
```

### Testing AWS Deployment:
Use `aws-test.html` (in project root) to test the full upload → extract → summarize pipeline via browser.

## Repository Status

- Current branch: `migration/aws-cloud`
- Main branch: `main`
- Status: AWS serverless deployment complete and running in production
- Production URL: https://d35sg48h6p3ej1.cloudfront.net
- API: https://g5oco2erb4.execute-api.us-east-1.amazonaws.com/prod/
- Local Flask app: Archived to `archive/flask-app/` (reference only)

## Common Workflows

**Deploy to AWS production**:
```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk deploy PodcastStackStack-prod
```

**Update frontend**:
```bash
# Edit index.html in project root
aws s3 cp index.html s3://BUCKET_NAME/index.html
aws cloudfront create-invalidation --distribution-id ID --paths "/*"
```

**Monitor production**:
```bash
# View Lambda logs
aws logs tail /aws/lambda/PodcastStack-prod-extract-transcript --follow

# View Step Functions executions
aws stepfunctions list-executions --state-machine-arn ARN

# Query DynamoDB
aws dynamodb scan --table-name PodcastStackStack-prod-jobs
```

**Update Lambda function code**:
```bash
cd aws-cloud/podcast_stack
# Edit lambda_functions/*/index.py
cdk deploy PodcastStackStack-prod
```

**Test locally before deploying**:
```bash
cdk synth PodcastStackStack-prod
cdk diff PodcastStackStack-prod
```

---

## Archived: Local Flask Application

**IMPORTANT**: This section documents the archived Flask implementation. It is NOT used in production.

**Location**: `archive/flask-app/`
**Status**: Archived November 15, 2025
**Use**: Reference and local testing only

### When to Use Archived Flask App

Only use the Flask app for:
- Understanding original implementation logic
- Local development without AWS costs
- Testing TTML parsing offline
- Educational purposes

**Do NOT use for**:
- Production deployments
- Scalable processing
- Public-facing applications
- Multi-user scenarios

### Flask App Overview

**Entry point**: `archive/flask-app/app.py`

The Flask app provided:
- Web UI for uploading TTML files (templates/index.html, templates/result.html)
- TTML transcript extraction via XML parsing
- OpenAI GPT-3.5-turbo summarization with rate limiting and chunking
- Background file monitoring (`monitor_ttml.py`) that auto-detects new TTML files in Apple Podcasts cache and uploads them

Key functions in app.py:
- `extract_transcript(ttml_content, include_timestamps)` - Parses TTML XML (namespace: `http://www.w3.org/ns/ttml`), extracts text from `<p>` and `<span>` elements
- `summarize_transcript(transcript)` - Chunks transcript into 4000-char blocks, calls OpenAI API with exponential backoff retry logic (up to 8 retries, 60s max wait, 3s delay between chunks)
- `/upload` - Web form endpoint accepting file uploads with optional timestamp inclusion
- `/upload_api` - JSON API endpoint for programmatic uploads

**Auto-monitoring**: app.py:17 spawned monitor_ttml.py as background subprocess, which watched `~/Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML` and auto-uploaded new .ttml files to the Flask API.

### Running Flask App (Archived)

**See `archive/flask-app/README.md` for complete instructions.**

Quick reference:
```bash
cd archive/flask-app
python3 -m venv venv
source venv/bin/activate
pip install -r flask-requirements.txt
# Create .env in project root with OPENAI_API_KEY
python app.py
# Access at http://127.0.0.1:5000/
```

### Flask App Limitations

- Requires macOS with Apple Podcasts app for auto-monitoring
- Single-threaded, no scalability
- Local storage only (no cloud backup)
- Manual file management
- No global distribution
- No job tracking/persistence

### Migration Notes

Flask code was migrated to Lambda functions:
- `app.py:extract_transcript()` → `lambda_functions/extract_transcript/index.py`
- `app.py:summarize_transcript()` → `lambda_functions/summarize_transcript/index.py`
- Flask templates → `index.html` (CloudFront static site)
- Local file storage → S3 buckets
- No database → DynamoDB job tracking

See `MIGRATION_COMPLETE.md` for detailed migration history.
