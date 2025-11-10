"""
Lambda function to get job status and result URLs.
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from botocore.config import Config

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

STORAGE_BUCKET = os.environ['STORAGE_BUCKET']
JOB_TABLE = os.environ['JOB_TABLE']


def generate_signed_url(key):
    """Generate signed URL for S3 object."""
    if not key:
        return None
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': STORAGE_BUCKET, 'Key': key},
            ExpiresIn=3600  # 1 hour
        )
    except Exception as e:
        print(f"Error generating signed URL for {key}: {str(e)}")
        return None


def handler(event, context):
    """Get job status and result URLs."""
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        job_id = query_params.get('jobId')
        
        if not job_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'jobId is required'})
            }
        
        # Get job from DynamoDB
        table = dynamodb.Table(JOB_TABLE)
        response = table.get_item(Key={'jobId': job_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Job not found'})
            }
        
        job = response['Item']
        
        # Build response
        result = {
            'jobId': job_id,
            'status': job.get('status', 'unknown'),
            'createdAt': job.get('createdAt'),
            'updatedAt': job.get('updatedAt')
        }
        
        # Add signed URLs if available
        if 'transcriptKey' in job:
            result['transcriptUrl'] = generate_signed_url(job['transcriptKey'])
        
        if 'summaryKey' in job:
            result['summaryUrl'] = generate_signed_url(job['summaryKey'])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        print(f"Error getting result: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }

