# Deployment Guide

Complete guide for deploying and managing the podcast transcript extractor on AWS.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Setup](#first-time-setup)
3. [Deploying to Production](#deploying-to-production)
4. [Updating the Application](#updating-the-application)
5. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
6. [Cost Management](#cost-management)
7. [Security Best Practices](#security-best-practices)
8. [Disaster Recovery](#disaster-recovery)

## Prerequisites

### Required Tools

1. **AWS Account** with administrator access
2. **AWS CLI** configured with credentials
   ```bash
   aws configure
   # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)
   ```
3. **Docker Desktop** running (required for Lambda bundling)
4. **Python 3.12+** installed
5. **Node.js 18+** (for AWS CDK)
6. **OpenAI API Key** from https://platform.openai.com/api-keys

### Verify Installation

```bash
aws --version          # Should show AWS CLI 2.x
docker --version       # Should show Docker 20.x+
python3 --version      # Should show Python 3.12+
node --version         # Should show Node 18+
```

### AWS Account Limits

Ensure your account has sufficient limits:
- Lambda concurrent executions: At least 10
- API Gateway requests: At least 10,000/month
- S3 storage: At least 100GB
- DynamoDB read/write capacity: On-demand mode (no limits)

## First-Time Setup

### 1. Clone Repository

```bash
git clone https://github.com/saikamat/podcast-transcript-extractor.git
cd apple-podcast-transcript-extractor
```

### 2. Install CDK

```bash
npm install -g aws-cdk
cdk --version  # Should show 2.x
```

### 3. Bootstrap AWS Environment

**Only needed once per AWS account/region combination.**

```bash
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1
```

Replace `YOUR_ACCOUNT_ID` with your 12-digit AWS account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### 4. Store OpenAI API Key

```bash
aws secretsmanager create-secret \
  --name podcast-app/openai-key-prod \
  --secret-string '{"OPENAI_API_KEY":"sk-your-key-here"}' \
  --description "OpenAI API key for podcast transcript summarization"
```

**Verify secret:**
```bash
aws secretsmanager get-secret-value --secret-id podcast-app/openai-key-prod
```

### 5. Setup CDK Project

```bash
cd aws-cloud/podcast_stack
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 6. Review Configuration

Edit `podcast_stack/podcast_stack_stack.py` if needed:

```python
# Key configurations:
ENVIRONMENT = "prod"
LAMBDA_MEMORY_EXTRACT = 512     # MB
LAMBDA_MEMORY_SUMMARIZE = 1024  # MB
S3_UPLOAD_LIFECYCLE_DAYS = 30
S3_TRANSCRIPT_LIFECYCLE_DAYS = 90
S3_SUMMARY_LIFECYCLE_DAYS = 180
```

### 7. Validate Stack

```bash
cdk synth PodcastStackStack-prod
```

This generates CloudFormation template. Review for errors.

## Deploying to Production

### Initial Deployment

```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk deploy PodcastStackStack-prod
```

**Deployment takes 5-10 minutes.**

**Expected output:**
```
Outputs:
PodcastStackStack-prod.ApiUrl = https://xyz.execute-api.us-east-1.amazonaws.com/prod/
PodcastStackStack-prod.CloudFrontUrl = https://d123.cloudfront.net
PodcastStackStack-prod.BucketName = podcaststackstack-prod-storage-xyz
```

**Save these values!**

### Update Frontend with API URL

1. Edit `index.html` in project root
2. Update API_BASE_URL:
   ```javascript
   const API_BASE_URL = 'https://YOUR_API_URL_FROM_OUTPUT/prod';
   ```
3. Upload to S3:
   ```bash
   aws s3 cp index.html s3://YOUR_BUCKET_NAME/index.html \
     --content-type "text/html" \
     --cache-control "max-age=300"
   ```
4. Invalidate CloudFront cache:
   ```bash
   # Get distribution ID
   aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items[0]=='d123.cloudfront.net'].Id" --output text

   # Invalidate
   aws cloudfront create-invalidation \
     --distribution-id YOUR_DISTRIBUTION_ID \
     --paths "/*"
   ```

### Verify Deployment

1. **Test API Gateway:**
   ```bash
   curl -X POST https://YOUR_API_URL/prod/presign \
     -H "Content-Type: application/json" \
     -d '{"filename": "test.ttml"}'
   ```

2. **Test CloudFront:**
   ```bash
   curl https://YOUR_CLOUDFRONT_URL
   ```

3. **Test full pipeline:**
   - Open CloudFront URL in browser
   - Upload a sample TTML file
   - Verify transcript and summary generation

## Updating the Application

### Update Lambda Functions

1. Edit Lambda code in `aws-cloud/podcast_stack/lambda_functions/*/index.py`
2. Deploy changes:
   ```bash
   cd aws-cloud/podcast_stack
   source .venv/bin/activate
   cdk diff PodcastStackStack-prod  # Review changes
   cdk deploy PodcastStackStack-prod
   ```

### Update Infrastructure

1. Edit CDK stack in `podcast_stack/podcast_stack_stack.py`
2. Review changes:
   ```bash
   cdk diff PodcastStackStack-prod
   ```
3. Deploy if satisfied:
   ```bash
   cdk deploy PodcastStackStack-prod
   ```

### Update Frontend Only

```bash
# Edit index.html
aws s3 cp index.html s3://YOUR_BUCKET_NAME/index.html \
  --content-type "text/html"

# Invalidate cache (critical!)
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

**Wait 1-2 minutes for invalidation to complete.**

### Update OpenAI API Key

```bash
aws secretsmanager update-secret \
  --secret-id podcast-app/openai-key-prod \
  --secret-string '{"OPENAI_API_KEY":"sk-new-key-here"}'
```

**No redeployment needed - Lambdas fetch from Secrets Manager at runtime.**

## Monitoring and Troubleshooting

### CloudWatch Logs

View Lambda logs in real-time:

```bash
# Extract transcript Lambda
aws logs tail /aws/lambda/PodcastStack-prod-extract-transcript --follow

# Summarize Lambda
aws logs tail /aws/lambda/PodcastStack-prod-summarize-transcript --follow

# Presign Lambda
aws logs tail /aws/lambda/PodcastStack-prod-presign --follow

# Get result Lambda
aws logs tail /aws/lambda/PodcastStack-prod-get-result --follow

# Start pipeline Lambda
aws logs tail /aws/lambda/PodcastStack-prod-start-pipeline --follow
```

### Step Functions Monitoring

View workflow executions:

```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT:stateMachine:PodcastStackStack-prod-TranscriptPipeline \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:ACCOUNT:execution:...
```

**Or use AWS Console:**
1. Navigate to Step Functions
2. Select `PodcastStackStack-prod-TranscriptPipeline`
3. View execution history and visual workflow

### DynamoDB Job Tracking

Query job status:

```bash
# Get specific job
aws dynamodb get-item \
  --table-name PodcastStackStack-prod-jobs \
  --key '{"jobId": {"S": "YOUR_JOB_ID"}}'

# Scan all jobs (expensive!)
aws dynamodb scan \
  --table-name PodcastStackStack-prod-jobs \
  --limit 10
```

### Common Issues

#### 1. Upload Fails (CORS Error)

**Symptoms:** Browser console shows CORS error
**Solution:**
- Verify S3 CORS configuration in CDK stack
- Check API Gateway CORS settings
- Ensure presigned URL hasn't expired (5-minute timeout)

#### 2. Processing Stuck

**Symptoms:** Job status stays "processing" for >5 minutes
**Debug:**
```bash
# Check Step Functions execution
aws stepfunctions list-executions \
  --state-machine-arn YOUR_STATE_MACHINE_ARN \
  --status-filter RUNNING

# Check Lambda logs for errors
aws logs tail /aws/lambda/PodcastStack-prod-extract-transcript --follow
```

**Common causes:**
- OpenAI API rate limiting (check summarize Lambda logs)
- Invalid TTML file format
- Lambda timeout (15-minute max)

#### 3. No Summary Generated

**Symptoms:** Transcript exists but summary is empty
**Debug:**
```bash
# Check summarize Lambda logs
aws logs filter-pattern /aws/lambda/PodcastStack-prod-summarize-transcript --filter-pattern "ERROR"
```

**Common causes:**
- OpenAI API key expired/invalid
- Rate limit exceeded
- Network timeout

**Fix:**
```bash
# Verify OpenAI key
aws secretsmanager get-secret-value --secret-id podcast-app/openai-key-prod

# Test OpenAI API manually
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"test"}]}'
```

#### 4. Lambda Deployment Fails

**Symptoms:** `cdk deploy` fails with bundling error
**Debug:**
```bash
# Ensure Docker is running
docker ps

# Check Lambda requirements.txt exists
ls aws-cloud/podcast_stack/lambda_functions/*/requirements.txt

# Try manual synth
cdk synth PodcastStackStack-prod
```

**Common causes:**
- Docker not running
- Missing requirements.txt in Lambda directories
- Platform mismatch (use `platform="linux/amd64"`)

## Cost Management

### Monthly Cost Estimate

**Typical usage (100 podcasts/month):**

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 100 executions × 5 min avg × 512MB | $0.50 |
| S3 | 10GB storage + requests | $0.30 |
| API Gateway | 500 requests | $0.02 |
| Step Functions | 100 executions | $0.03 |
| DynamoDB | 100 writes + 500 reads | $0.05 |
| CloudFront | 1GB transfer | $0.10 |
| OpenAI API | 100 summaries × 4000 tokens avg | $8.00 |
| **Total** | | **~$9/month** |

**Most cost is OpenAI API ($8). AWS infrastructure is <$1/month.**

### Cost Optimization Tips

1. **S3 Lifecycle Policies** (already configured):
   - Uploads deleted after 30 days
   - Transcripts deleted after 90 days
   - Summaries deleted after 180 days

2. **Lambda Memory Tuning:**
   - Monitor CloudWatch metrics
   - Reduce memory if usage is low (<50%)
   - Increase if hitting timeouts

3. **DynamoDB:**
   - Using PAY_PER_REQUEST (best for low traffic)
   - No idle costs

4. **CloudFront:**
   - Consider enabling compression
   - Use price class (All, 100, 200)

5. **Monitor with AWS Cost Explorer:**
   ```bash
   # View monthly costs
   aws ce get-cost-and-usage \
     --time-period Start=2025-11-01,End=2025-11-30 \
     --granularity MONTHLY \
     --metrics BlendedCost
   ```

### Set Budget Alerts

```bash
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget '{"BudgetName":"PodcastAppBudget","BudgetLimit":{"Amount":"20","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"your@email.com"}]}'
```

## Security Best Practices

### 1. IAM Least Privilege

Lambda execution roles already follow least privilege:
- Extract Lambda: Read S3 uploads, write transcripts, update DynamoDB
- Summarize Lambda: Read transcripts, write summaries, update DynamoDB, read Secrets Manager
- Presign Lambda: Write DynamoDB, generate presigned URLs
- Get Result Lambda: Read DynamoDB, generate presigned URLs

**Review roles:**
```bash
aws iam get-role --role-name PodcastStackStack-prod-ExtractLambdaRole
```

### 2. Secrets Management

- OpenAI key stored in Secrets Manager (encrypted at rest)
- Auto-rotated annually (configure in AWS console)
- Never log API keys in CloudWatch

### 3. S3 Security

- No public bucket access (all access via presigned URLs)
- Presigned URLs expire after 5 minutes (uploads) or 1 hour (downloads)
- CORS restricted to CloudFront domain

### 4. API Gateway

- CORS enabled only for CloudFront origin
- Rate limiting (10,000 requests/second burst)
- CloudWatch logging enabled

### 5. CloudFront

- HTTPS only (no HTTP)
- Custom domain optional (requires ACM certificate)
- WAF optional (for DDoS protection)

## Disaster Recovery

### Backup Strategy

**Automated (already configured):**
- S3 versioning: Disabled (not needed, processed files are ephemeral)
- DynamoDB: Point-in-time recovery: Disabled (jobs are transient)
- Lambda: Code in Git (infrastructure as code)

**Manual backups (if needed):**
```bash
# Export DynamoDB table
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:ACCOUNT:table/PodcastStackStack-prod-jobs \
  --s3-bucket YOUR_BACKUP_BUCKET \
  --s3-prefix dynamodb-backup/

# Backup S3 bucket
aws s3 sync s3://SOURCE_BUCKET s3://BACKUP_BUCKET --source-region us-east-1
```

### Recovery Procedures

#### 1. Stack Deletion (Accidental)

**Recover:**
```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk deploy PodcastStackStack-prod
```

**Note:** S3 bucket and DynamoDB table are retained (RETAIN policy), so data is safe.

#### 2. Lambda Corruption

```bash
# Redeploy from Git
git pull origin main
cd aws-cloud/podcast_stack
cdk deploy PodcastStackStack-prod
```

#### 3. Lost CloudFront URL

```bash
# Find distribution
aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='PodcastStackStack-prod CloudFront Distribution'].DomainName" --output text
```

#### 4. Lost API Gateway URL

```bash
# Find API
aws apigateway get-rest-apis --query "items[?name=='PodcastStackStack-prod-Api'].id" --output text

# Construct URL
echo "https://API_ID.execute-api.us-east-1.amazonaws.com/prod/"
```

### Region Failure (Extreme)

AWS us-east-1 region failure is rare. If needed:

1. Update CDK stack environment:
   ```python
   env=cdk.Environment(account="YOUR_ACCOUNT", region="us-west-2")
   ```
2. Bootstrap new region:
   ```bash
   cdk bootstrap aws://ACCOUNT/us-west-2
   ```
3. Redeploy:
   ```bash
   cdk deploy PodcastStackStack-prod
   ```
4. Recreate Secrets Manager secret in new region

## Teardown / Deletion

### Delete Stack (Retain Data)

```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk destroy PodcastStackStack-prod
```

**Retained resources (must delete manually):**
- S3 bucket: `podcaststackstack-prod-storage-*`
- DynamoDB table: `PodcastStackStack-prod-jobs`

**Deleted automatically:**
- Lambda functions
- API Gateway
- Step Functions
- CloudFront distribution (takes 15-30 minutes)
- IAM roles

### Delete Retained Resources

```bash
# Delete S3 bucket (empties first)
aws s3 rb s3://BUCKET_NAME --force

# Delete DynamoDB table
aws dynamodb delete-table --table-name PodcastStackStack-prod-jobs

# Delete Secrets Manager secret
aws secretsmanager delete-secret \
  --secret-id podcast-app/openai-key-prod \
  --force-delete-without-recovery
```

### Verify Complete Deletion

```bash
# Check CloudFormation stacks
aws cloudformation list-stacks --query "StackSummaries[?StackName=='PodcastStackStack-prod'].StackStatus" --output text

# Should return empty or DELETE_COMPLETE
```

## Support and Resources

- **AWS CDK Documentation:** https://docs.aws.amazon.com/cdk/
- **AWS Lambda Best Practices:** https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
- **OpenAI API Docs:** https://platform.openai.com/docs/
- **Project Repository:** https://github.com/saikamat/podcast-transcript-extractor
- **CloudWatch Insights:** Use for advanced log analysis

## Changelog

- **2025-11-15:** Initial cloud deployment guide created
- **2025-11-15:** Added CloudFront CDN and frontend hosting
- **2025-11-15:** Migrated from Flask to AWS serverless
