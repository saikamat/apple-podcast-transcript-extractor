"""
Lambda function to generate presigned URL for S3 upload.
"""

import json
import boto3
import os
import uuid
from datetime import datetime, timedelta
from botocore.config import Config

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

STORAGE_BUCKET = os.environ['STORAGE_BUCKET']
JOB_TABLE = os.environ['JOB_TABLE']


def handler(event, context):
    """Generate presigned URL for file upload."""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename', 'upload.ttml')
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create S3 key
        s3_key = f"uploads/{job_id}_{filename}"
        
        # Generate presigned URL (15 min expiry)
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': STORAGE_BUCKET, 'Key': s3_key},
            ExpiresIn=900  # 15 minutes
        )
        
        # Create job record in DynamoDB
        table = dynamodb.Table(JOB_TABLE)
        table.put_item(
            Item={
                'jobId': job_id,
                'status': 'uploading',
                'filename': filename,
                's3Key': s3_key,
                'createdAt': datetime.utcnow().isoformat(),
                'updatedAt': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'jobId': job_id,
                'uploadUrl': presigned_url,
                's3Key': s3_key
            })
        }
        
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }

