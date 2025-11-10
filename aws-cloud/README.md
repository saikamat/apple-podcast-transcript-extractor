# AWS Cloud Migration - Podcast Transcript Summarizer

This directory contains the complete infrastructure for migrating the podcast transcript summarizer to AWS.

## 📁 Directory Structure

```
aws-cloud/
├── podcast_stack/              # CDK Infrastructure
│   ├── app.py                  # CDK app entry point
│   ├── podcast_stack/           # Stack definitions
│   │   └── podcast_stack_stack.py
│   ├── lambda_functions/       # Lambda function code
│   │   ├── extract_transcript/
│   │   ├── summarize_transcript/
│   │   ├── presign/
│   │   └── get_result/
│   ├── frontend/               # Upload UI
│   │   └── index.html
│   └── requirements.txt        # Python dependencies
├── DEPLOYMENT.md               # Step-by-step deployment guide
├── MIGRATION_SUMMARY.md        # Architecture comparison & changes
└── README.md                   # This file
```

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   cd aws-cloud/podcast_stack
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure AWS**
   ```bash
   aws configure
   ```

3. **Store Secrets**
   ```bash
   aws secretsmanager create-secret \
     --name podcast-app/openai-key-dev \
     --secret-string '{"OPENAI_API_KEY":"your-key"}'
   ```

4. **Update Account ID**
   Edit `app.py` with your AWS account ID

5. **Bootstrap CDK**
   ```bash
   cdk bootstrap aws://ACCOUNT-ID/REGION
   ```

6. **Deploy**
   ```bash
   cdk deploy PodcastStackStack-dev
   ```

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)**: Complete deployment instructions
- **[MIGRATION_SUMMARY.md](./MIGRATION_SUMMARY.md)**: Architecture details and comparison

## 🏗️ Architecture

```
User → Frontend (S3) → API Gateway → Lambda (Presign) → S3 Upload
                                                     ↓
                                    Step Functions → Extract → Summarize
                                                     ↓
                                    DynamoDB ← Result URLs
```

## 🎯 Features

- ✅ Serverless architecture (no servers to manage)
- ✅ Automatic scaling
- ✅ Presigned S3 uploads (direct to S3)
- ✅ Asynchronous processing with Step Functions
- ✅ Job tracking with DynamoDB
- ✅ Environment separation (dev/prod)
- ✅ Automatic cleanup (lifecycle policies)
- ✅ Cost-optimized for low traffic

## 💰 Estimated Costs

For <100 requests/day: **~$5-15/month**
- S3: $0-2
- Lambda: $0-5
- DynamoDB: $0-1
- API Gateway: $0-1
- Step Functions: $0-5
- OpenAI API: $5-10

## 🔧 What Changed

### Removed
- ❌ Local file system monitoring (`monitor_ttml.py`)
- ❌ MacBook-specific paths
- ❌ Flask dev server
- ❌ In-memory processing

### Added
- ✅ AWS CDK Infrastructure as Code
- ✅ Presigned S3 upload URLs
- ✅ Asynchronous Step Functions workflow
- ✅ DynamoDB job tracking
- ✅ Environment-specific configs (dev/prod)
- ✅ Secrets Manager for API keys
- ✅ Modern frontend with drag-and-drop

## 🚦 Status

✅ Infrastructure code complete  
✅ Lambda functions implemented  
✅ Frontend built  
✅ Documentation created  
⏳ Ready for deployment  

## 📝 Next Steps

1. Follow [DEPLOYMENT.md](./DEPLOYMENT.md) to deploy
2. Test with a sample TTML file
3. Monitor costs and usage
4. Set up CloudWatch alarms
5. Deploy to production when ready

## ❓ Questions?

See the deployment guide or migration summary for detailed information.

