# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A podcast transcript extractor and summarizer that processes Apple Podcasts TTML files. The project has two architectures:
1. **Local Flask app** (app.py) - Original implementation for local development
2. **AWS serverless** (aws-cloud/) - Cloud migration using AWS CDK, Lambda, Step Functions, and S3

**Limitation**: Requires Apple Podcasts app running on macOS with manually downloaded podcast episodes to access TTML cache files.

## Core Architecture

### Local Flask Application

**Entry point**: `app.py`

The Flask app provides:
- Web UI for uploading TTML files (templates/index.html, templates/result.html)
- TTML transcript extraction via XML parsing
- OpenAI GPT-3.5-turbo summarization with rate limiting and chunking
- Background file monitoring (`monitor_ttml.py`) that auto-detects new TTML files in Apple Podcasts cache and uploads them

Key functions in app.py:
- `extract_transcript(ttml_content, include_timestamps)` - Parses TTML XML (namespace: `http://www.w3.org/ns/ttml`), extracts text from `<p>` and `<span>` elements
- `summarize_transcript(transcript)` - Chunks transcript into 4000-char blocks, calls OpenAI API with exponential backoff retry logic (up to 8 retries, 60s max wait, 3s delay between chunks)
- `/upload` - Web form endpoint accepting file uploads with optional timestamp inclusion
- `/upload_api` - JSON API endpoint for programmatic uploads

**Auto-monitoring**: app.py:17 spawns monitor_ttml.py as background subprocess, which watches `~/Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/TTML` and auto-uploads new .ttml files to the Flask API.

### AWS Cloud Architecture

**Directory**: `aws-cloud/podcast_stack/`

Serverless event-driven pipeline:
1. Frontend requests presigned S3 URL from API Gateway
2. File uploads directly to S3 `uploads/` prefix
3. S3 event triggers `start_pipeline` Lambda
4. Step Functions orchestrates: Extract Lambda → Summarize Lambda
5. Results stored in S3 (`transcripts/`, `summaries/`)
6. Job status tracked in DynamoDB

**CDK Stack**: `podcast_stack/podcast_stack_stack.py`
- Two environments: dev and prod (detected via construct_id)
- Dev: shorter lifecycles (7/30/90 days), smaller memory (256MB/512MB), auto-delete on destroy
- Prod: longer lifecycles (30/90/180 days), more memory (512MB/1024MB), retain on destroy

**Lambda Functions**:
- `lambda_functions/presign/` - Generates S3 presigned PUT URLs, creates DynamoDB job records
- `lambda_functions/start_pipeline/` - Triggered by S3 uploads, starts Step Functions execution
- `lambda_functions/extract_transcript/` - Ports app.py extraction logic, reads from S3, writes to S3/DynamoDB
- `lambda_functions/summarize_transcript/` - Ports app.py summarization logic with OpenAI, writes to S3/DynamoDB
- `lambda_functions/get_result/` - Queries DynamoDB, returns presigned GET URLs for results

## Development Commands

### Local Flask App

**Setup**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Environment**: Create `.env` file with:
```
OPENAI_API_KEY=your_key_here
```

**Run**:
```bash
python app.py
```
Starts Flask on http://127.0.0.1:5000/

**File monitoring** (runs automatically with app.py, but can run standalone):
```bash
python monitor_ttml.py
```

**Test OpenAI API connection**:
```bash
python tests/test_openAI_API.py
```

**View saved transcripts** (starts viewer Flask app on port 5000):
```bash
python viewer.py
```

### AWS Cloud Deployment

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
  --name podcast-app/openai-key-dev \
  --secret-string '{"OPENAI_API_KEY":"your-key"}'
```

**Bootstrap CDK** (first time per account/region):
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

**Deploy dev**:
```bash
cd aws-cloud/podcast_stack
cdk deploy PodcastStackStack-dev
```

**Deploy prod**:
```bash
cdk deploy PodcastStackStack-prod
```

**Destroy**:
```bash
cdk destroy PodcastStackStack-dev
```

**View diffs**:
```bash
cdk diff PodcastStackStack-dev
```

**Synthesize CloudFormation**:
```bash
cdk synth
```

## Key Technical Details

### TTML Parsing
- Uses `xml.etree.ElementTree` with namespace `http://www.w3.org/ns/ttml`
- Searches for `<p>` elements, extracts text from nested `<span>` elements
- Optional timestamps from `begin` attribute (formatted as HH:MM:SS)

### OpenAI Rate Limiting Strategy
Both local and Lambda implementations use:
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

**Local application**:
- `app.py` - Main Flask application with transcript extraction and summarization
- `monitor_ttml.py` - Watches Apple Podcasts TTML cache directory, auto-uploads to Flask API
- `viewer.py` - Flask app to browse and download saved transcripts from `./transcripts/` directory
- `clean_ttml.py` - Utility script for TTML file processing
- `tests/test_openAI_API.py` - Simple OpenAI API connectivity test
- `tests/database_cap_check.py` - Database capacity checking utility

**AWS serverless**:
- `aws-cloud/DEPLOYMENT.md` - Step-by-step AWS deployment guide
- `aws-cloud/MIGRATION_SUMMARY.md` - Architecture comparison and migration details
- `aws-cloud/podcast_stack/app.py` - CDK app entry point (defines dev/prod stacks)
- `aws-cloud/podcast_stack/podcast_stack/podcast_stack_stack.py` - Infrastructure definition (S3, Lambda, Step Functions, DynamoDB, API Gateway)
- `aws-cloud/podcast_stack/lambda_functions/*/index.py` - Lambda function implementations

## Environment Variables

### Local Flask
- `OPENAI_API_KEY` - Required, from .env file

### AWS Lambda
- `STORAGE_BUCKET` - S3 bucket name (set by CDK)
- `JOB_TABLE` - DynamoDB table name (set by CDK)
- `SECRET_NAME` - Secrets Manager secret name (set by CDK)
- `STATE_MACHINE_ARN` - Step Functions ARN (set by CDK, starter Lambda only)
- `BUCKET_NAME` - Duplicate of STORAGE_BUCKET (starter Lambda only)

## Testing

### Local Flask App
**Web UI**: Navigate to http://127.0.0.1:5000/ and upload a TTML file

**API endpoint**:
```bash
curl -X POST http://127.0.0.1:5000/upload_api \
  -F "file=@path/to/file.ttml"
```

**Verify OpenAI API**:
```bash
python tests/test_openAI_API.py
```

### AWS Cloud
See aws-cloud/DEPLOYMENT.md "Testing" section for presigned URL workflow and API endpoint testing with curl.

## Project Directory Structure

```
.
├── app.py                    # Main Flask app
├── monitor_ttml.py           # TTML file watcher
├── viewer.py                 # Transcript viewer app
├── clean_ttml.py             # TTML processing utility
├── requirements.txt          # Python dependencies for local app
├── templates/                # Flask HTML templates
├── uploads/                  # Uploaded TTML files
├── transcripts/              # Processed transcripts and summaries
├── cache/                    # JSON cache files
├── tests/                    # Test scripts
├── .env                      # Environment variables (create this, not in git)
└── aws-cloud/                # AWS serverless implementation
    ├── DEPLOYMENT.md         # AWS deployment instructions
    ├── MIGRATION_SUMMARY.md  # Architecture comparison
    └── podcast_stack/        # CDK project
        ├── app.py            # CDK app entry point
        ├── requirements.txt  # CDK Python dependencies
        ├── lambda_functions/ # Lambda function code
        │   ├── presign/
        │   ├── start_pipeline/
        │   ├── extract_transcript/
        │   ├── summarize_transcript/
        │   └── get_result/
        └── podcast_stack/    # CDK stack definitions
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
- Status: AWS migration complete and deployed to dev environment
- Production: Local Flask app (app.py) remains the active implementation

## Common Workflows

**Quick start for local development**:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=your_key" > .env
python app.py
```

**Deploy AWS dev environment**:
```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk deploy PodcastStackStack-dev
```

**View saved transcripts locally**:
```bash
python viewer.py
# Navigate to http://127.0.0.1:5000/
```
