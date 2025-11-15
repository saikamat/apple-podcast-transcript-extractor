# Cloud Migration Summary: Podcast Transcript Summarizer

## Migration Overview

This document outlines the cloud migration of the local Flask-based podcast transcript summarizer to a fully serverless AWS production architecture.

## Architecture Comparison

### Before (Local)
```
┌─────────────────┐
│   Flask App     │
│   (app.py)      │
├─────────────────┤
│  - Upload UI    │
│  - Extraction   │
│  - Summarization│
└─────────────────┘
        ↓
┌─────────────────┐
│  Local Storage  │
│  - uploads/     │
│  - cache/       │
└─────────────────┘
```

### After (Cloud)
```
┌─────────────────────────────────────────────────────────────┐
│                        S3 Bucket                             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │  uploads/   │→ │ transcripts/ │→ │  summaries/    │    │
│  └─────────────┘  └──────────────┘  └────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                    Step Functions                            │
│  ┌──────────────┐         ┌──────────────┐                   │
│  │ Lambda:      │   →     │ Lambda:      │                   │
│  │ Extract      │         │ Summarize    │                   │
│  └──────────────┘         └──────────────┘                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    API Gateway                               │
│  POST /presign  →  GET /result                              │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (S3/Netlify)                    │
│              Upload form with presigned URLs                │
└─────────────────────────────────────────────────────────────┘
```

## Key Changes

### 1. **File Upload Flow**
- **Before**: Direct Flask POST upload
- **After**: Presigned S3 PUT URLs
  - Frontend requests presigned URL from API
  - Uploads directly to S3 (bypassing API)
  - More scalable and cost-effective

### 2. **Processing Pipeline**
- **Before**: Synchronous in-memory processing
- **After**: Asynchronous Step Functions workflow
  - Extract → Summarize stages
  - Parallel processing possible
  - Better error handling and retries

### 3. **Storage**
- **Before**: Local file system (`uploads/`, `cache/`)
- **After**: S3 with lifecycle policies
  - Automatic cleanup after expiration
  - Versioning enabled
  - Cross-region replication possible

### 4. **State Management**
- **Before**: No persistent state tracking
- **After**: DynamoDB table for job metadata
  - Job status, file keys, timestamps
  - Query-able job history
  - Easy to add features like job listing

### 5. **Dependencies**
- **Before**: 
  - `monitor_ttml.py` watching local directory
  - Hardcoded MacBook paths
- **After**:
  - User-initiated uploads via web UI
  - No dependency on local file system
  - Cross-platform compatible

## Code Migration Details

### Lambda Functions Created

1. **`extract_transcript`** (`lambda_functions/extract_transcript/`)
   - Ported from `app.py:extract_transcript()`
   - Downloads TTML from S3
   - Parses XML, extracts text
   - Saves transcript to S3
   - Updates DynamoDB job status

2. **`summarize_transcript`** (`lambda_functions/summarize_transcript/`)
   - Ported from `app.py:summarize_transcript()`
   - Downloads transcript from S3
   - Chunks text (4000 chars)
   - Calls OpenAI GPT-3.5-turbo
   - Handles rate limits with exponential backoff
   - Saves summary to S3
   - Updates DynamoDB job status

3. **`presign`** (`lambda_functions/presign/`)
   - Generates presigned S3 PUT URL
   - Creates DynamoDB job record
   - Returns job ID and upload URL

4. **`get_result`** (`lambda_functions/get_result/`)
   - Queries DynamoDB for job status
   - Generates presigned GET URLs for results
   - Returns transcript and summary URLs

### Infrastructure as Code (CDK)

**File**: `podcast_stack/podcast_stack_stack.py`

Defines:
- S3 bucket with lifecycle rules
- DynamoDB table for job tracking
- Lambda functions with IAM roles
- Step Functions state machine
- API Gateway with CORS
- Secrets Manager integration

### Frontend

**File**: `frontend/index.html`

Modern SPA with:
- Drag-and-drop file upload
- Progress tracking
- Job polling
- Result display
- Responsive design

## Deployment Files

```
aws-cloud/
├── podcast_stack/
│   ├── app.py                          # CDK app entry point
│   ├── podcast_stack/
│   │   └── podcast_stack_stack.py      # Stack definition
│   ├── cdk.json                        # CDK configuration
│   ├── requirements.txt                 # Python dependencies
│   └── lambda_functions/
│       ├── extract_transcript/
│       ├── summarize_transcript/
│       ├── presign/
│       └── get_result/
├── frontend/
│   └── index.html                      # Upload UI
├── DEPLOYMENT.md                       # Deployment guide
└── MIGRATION_SUMMARY.md               # This file
```

## Production Configuration

The serverless architecture uses production-grade settings:

- S3 retention: 30 days (uploads), 90 days (transcripts), 180 days (summaries)
- Extract Lambda: 512MB memory, 120s timeout
- Summarize Lambda: 1024MB memory, 300s timeout
- Other Lambdas: 256MB memory, 10-30s timeout
- Removal policy: RETAIN (data preserved on stack deletion)
- Auto-delete: False (manual cleanup required for safety)

## Security Enhancements

1. **Secrets Management**: OpenAI API key in AWS Secrets Manager
2. **IAM Roles**: Least-privilege access for Lambda functions
3. **CORS Configuration**: API Gateway and S3 CORS rules
4. **Presigned URLs**: Time-limited, scoped access
5. **S3 Encryption**: Enable at-rest encryption
6. **VPC** (optional): Isolate Lambda functions

## Cost Comparison

### Local (Current)
- **Infrastructure**: $0 (runs on personal machine)
- **OpenAI API**: ~$5-10/month
- **Total**: ~$5-10/month

### Cloud (Projected)
- **Lambda**: ~$0-5/month
- **S3**: ~$0-2/month
- **DynamoDB**: ~$0-1/month
- **API Gateway**: ~$0-1/month
- **Step Functions**: ~$0-5/month
- **OpenAI API**: ~$5-10/month
- **Total**: ~$5-24/month

**Note**: Cloud adds ~$10-15/month for infrastructure, but provides:
- Scalability
- Availability
- No local dependencies
- Multi-user capability
- Automatic backups

## Migration Checklist

- [x] Create CDK project structure
- [x] Define infrastructure stack
- [x] Port extraction logic to Lambda
- [x] Port summarization logic to Lambda
- [x] Create API Gateway handlers
- [x] Build frontend UI
- [x] Create deployment documentation
- [x] Configure AWS credentials
- [x] Store OpenAI API key in Secrets Manager
- [x] Update account ID in app.py
- [x] Bootstrap CDK environment
- [x] Deploy production environment
- [x] Test end-to-end flow
- [x] Update frontend with API endpoint
- [x] Simplify to single production environment
- [ ] Set up monitoring/alarms (optional)
- [ ] Configure CI/CD (optional)

## Next Steps

1. **Monitor Usage**: Check AWS Cost Explorer regularly
2. **Set Up Alarms**: CloudWatch alarms for errors (optional)
3. **Domain Setup**: Configure custom domain (optional)
4. **Authentication**: Add user auth if needed (Cognito)
5. **Analytics**: Add usage tracking (optional)
6. **Optimize Costs**: Review and adjust retention policies as needed

## Rollback Plan

If needed, you can:
1. Keep local Flask app running
2. Switch DNS/endpoint back to local
3. Export data from S3 if needed
4. Destroy cloud resources with `cdk destroy`

## Questions?

Refer to:
- `DEPLOYMENT.md` for deployment instructions
- AWS CDK documentation: https://docs.aws.amazon.com/cdk/
- Lambda best practices: https://docs.aws.amazon.com/lambda/

