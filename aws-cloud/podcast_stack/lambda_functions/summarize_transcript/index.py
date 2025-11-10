"""
Lambda function to summarize transcript using OpenAI GPT.
Ported from app.py:summarize_transcript()
"""

import json
import boto3
import os
import time
from datetime import datetime
from openai import OpenAI, RateLimitError

s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')

STORAGE_BUCKET = os.environ['STORAGE_BUCKET']
JOB_TABLE = os.environ['JOB_TABLE']
SECRET_NAME = os.environ['SECRET_NAME']


def get_openai_client():
    """Get OpenAI client with API key from Secrets Manager."""
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    secret_string = response['SecretString']

    # Try to parse as JSON first
    try:
        secret_dict = json.loads(secret_string)
        api_key = secret_dict['OPENAI_API_KEY']
    except (json.JSONDecodeError, KeyError):
        # Fallback: treat as plain string
        api_key = secret_string

    return OpenAI(api_key=api_key)


def summarize_transcript(transcript, client):
    """Summarize transcript using OpenAI."""
    max_chunk_size = 4000
    transcript_chunks = [transcript[i:i + max_chunk_size] for i in range(0, len(transcript), max_chunk_size)]
    
    summaries = []
    
    for i, chunk in enumerate(transcript_chunks):
        if i > 0:
            time.sleep(3)  # Rate limit delay
        
        retry_count = 0
        max_retries = 8
        success = False
        
        while retry_count < max_retries and not success:
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes podcast transcripts."},
                        {"role": "user", "content": f"Summarize the following podcast transcript in bullet points:\n\n{chunk}"}
                    ],
                    max_tokens=300
                )
                summaries.append(response.choices[0].message.content.strip())
                success = True
            except RateLimitError as e:
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(f"An error occurred: {e}")
                break
        
        if not success:
            summaries.append("*[This section could not be summarized due to API limitations]*")
    
    return "\n\n".join(summaries)


def handler(event, context):
    """Lambda handler for summarizing transcript."""
    try:
        job_id = event['jobId']
        transcript_key = event.get('transcriptKey', f"transcripts/{job_id}.txt")
        
        # Download transcript from S3
        response = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=transcript_key)
        transcript = response['Body'].read().decode('utf-8')
        
        # Get OpenAI client
        openai_client = get_openai_client()
        
        # Summarize transcript
        summary = summarize_transcript(transcript, openai_client)
        
        # Save summary to S3
        summary_key = f"summaries/{job_id}.txt"
        s3_client.put_object(
            Bucket=STORAGE_BUCKET,
            Key=summary_key,
            Body=summary.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Update job table
        table = dynamodb.Table(JOB_TABLE)
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #status = :status, summaryKey = :summaryKey, #updated = :updated',
            ExpressionAttributeNames={
                '#status': 'status',
                '#updated': 'updatedAt'
            },
            ExpressionAttributeValues={
                ':status': 'completed',
                ':summaryKey': summary_key,
                ':updated': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'jobId': job_id,
            'summaryKey': summary_key
        }
        
    except Exception as e:
        print(f"Error summarizing transcript: {str(e)}")
        raise

