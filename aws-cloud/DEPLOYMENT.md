# Deployment Guide: Podcast Transcript Summarizer to AWS

This guide walks you through deploying the podcast transcript summarizer application to AWS using Infrastructure as Code.

## Prerequisites

1. **AWS Account**: You need an active AWS account
2. **AWS CLI**: Install and configure AWS CLI
3. **CDK**: AWS CDK is installed via Python dependencies
4. **Python 3.11+**: Required for CDK and Lambda functions

## Setup Steps

### 1. Configure AWS Credentials

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)

### 2. Set Up Python Virtual Environment

```bash
cd aws-cloud/podcast_stack
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Bootstrap CDK (First Time Only)

CDK needs to create resources in your AWS account:

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Replace `ACCOUNT-ID` with your AWS account ID and `REGION` with your region (e.g., `us-east-1`).

Find your account ID:
```bash
aws sts get-caller-identity
```

### 4. Store OpenAI API Key

Create secrets in AWS Secrets Manager:

**For Dev:**
```bash
aws secretsmanager create-secret \
  --name podcast-app/openai-key-dev \
  --secret-string '{"OPENAI_API_KEY":"your-key-here"}' \
  --region us-east-1
```

**For Prod:**
```bash
aws secretsmanager create-secret \
  --name podcast-app/openai-key-prod \
  --secret-string '{"OPENAI_API_KEY":"your-key-here"}' \
  --region us-east-1
```

### 5. Update Account ID in app.py

Edit `aws-cloud/podcast_stack/app.py` and replace the empty account strings with your actual AWS account ID.

## Deployment

### Deploy Dev Environment

```bash
cd aws-cloud/podcast_stack
source .venv/bin/activate
cdk deploy PodcastStackStack-dev
```

CDK will show you what resources will be created. Type `y` to proceed.

### Deploy Prod Environment

```bash
cdk deploy PodcastStackStack-prod
```

## Post-Deployment Steps

### 1. Get API Endpoint

After deployment, CDK will output the API endpoint:

```
PodcastStackStack-dev:ApiEndpoint = https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/
```

### 2. Update Frontend

Edit `aws-cloud/podcast_stack/frontend/index.html`:
- Replace `YOUR_API_ID` with your actual API Gateway ID

### 3. Deploy Frontend (Optional)

Upload the frontend to an S3 bucket or use GitHub Pages, Netlify, or similar.

## Testing

### Test the API Endpoints

**1. Get Presigned URL:**
```bash
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/presign \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.ttml"}'
```

**2. Upload File:**
```bash
curl -X PUT "YOUR_PRESIGNED_URL" \
  --upload-file /path/to/file.ttml
```

**3. Check Status:**
```bash
curl "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/result?jobId=YOUR_JOB_ID"
```

## Environment Differences

| Resource | Dev | Prod |
|----------|-----|------|
| S3 Lifecycle | 7 days (uploads), 30 days (transcripts) | 30 days (uploads), 90 days (transcripts), 180 days (summaries) |
| Lambda Memory | 256MB | 512MB-1024MB |
| Lambda Timeout | 60-120s | 120-300s |
| Removal Policy | DESTROY | RETAIN |
| Logging | DEBUG | INFO |

## Cleanup

### Destroy Dev Environment

```bash
cdk destroy PodcastStackStack-dev
```

### Destroy Prod Environment

```bash
cdk destroy PodcastStackStack-prod
```

**Warning**: This will delete all resources, including data in S3 and DynamoDB.

## Troubleshooting

### CDK Bootstrap Issues

If you get "not bootstrapped" error:
```bash
cdk bootstrap
```

### Lambda Timeout

If processing times out:
1. Increase Lambda timeout in the stack
2. Increase Step Functions timeout
3. Use larger Lambda memory size

### OpenAI Rate Limits

If you hit rate limits:
1. Increase retry delays in `summarize_transcript/index.py`
2. Add exponential backoff
3. Consider using GPT-4o-mini for faster responses

### CORS Issues

If browser shows CORS errors:
1. Verify CORS settings in API Gateway
2. Check S3 bucket CORS configuration
3. Ensure frontend uses correct API endpoint

## Cost Estimation

For <100 requests/day:
- **Lambda**: ~$0-5/month
- **S3**: ~$0-2/month  
- **DynamoDB**: ~$0-1/month
- **API Gateway**: ~$0-1/month
- **Step Functions**: ~$0-5/month
- **CloudWatch**: ~$0-1/month

**Total**: ~$0-15/month

Actual costs depend on:
- File sizes
- Processing frequency
- Data retention
- Logging verbosity

## Security Notes

1. **Secrets**: Never commit API keys to git
2. **IAM Roles**: Lambda roles follow least-privilege principle
3. **S3 Access**: Files have lifecycle policies to auto-delete
4. **CORS**: Configure CORS to only allow your frontend domain
5. **API Keys**: Consider adding API keys for production

## Next Steps

1. Set up CI/CD with GitHub Actions
2. Add CloudWatch alarms for errors
3. Configure custom domain for API Gateway
4. Add user authentication (Cognito)
5. Implement rate limiting
6. Add monitoring dashboard

