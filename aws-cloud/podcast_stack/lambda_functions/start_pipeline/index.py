import os
import json
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')

JOB_TABLE = os.environ['JOB_TABLE']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
BUCKET_NAME = os.environ['BUCKET_NAME']


def handler(event, context):
    # S3 put event -> kick off Step Functions with jobId and ttmlKey
    # Key format from presign: uploads/{jobId}_{filename}
    try:
        # Get first record
        record = event['Records'][0]
        s3_info = record['s3']
        bucket = s3_info['bucket']['name']
        key = s3_info['object']['key']

        if not key.startswith('uploads/'):
            return { 'statusCode': 200, 'body': 'Ignored non-uploads key' }

        # Parse jobId from key
        filename = key.split('/')[-1]
        job_id = filename.split('_', 1)[0]

        # Update job status to processing
        table = dynamodb.Table(JOB_TABLE)
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #status = :status, s3Key = :s3key, updatedAt = :updated',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'processing',
                ':s3key': key,
                ':updated': datetime.utcnow().isoformat()
            }
        )

        # Start Step Functions execution
        input_payload = {
            'jobId': job_id,
            'ttmlKey': key
        }

        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(input_payload)
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Started', 'jobId': job_id})
        }
    except Exception as e:
        print(f"Error starting pipeline: {e}")
        raise
