"""
Lambda function to extract transcript from TTML file.
Ported from app.py:extract_transcript()
"""

import json
import xml.etree.ElementTree as ET
import boto3
import os
from datetime import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

STORAGE_BUCKET = os.environ['STORAGE_BUCKET']
JOB_TABLE = os.environ['JOB_TABLE']


def format_timestamp(seconds):
    """Format seconds into HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"


def extract_transcript(ttml_content, include_timestamps=False):
    """Extract transcript from TTML content."""
    try:
        root = ET.fromstring(ttml_content)
        transcript = []

        # Find all <p> elements in the TTML file
        paragraphs = root.findall(".//{http://www.w3.org/ns/ttml}p")

        for paragraph in paragraphs:
            paragraph_text = ""
            for span in paragraph.findall(".//{http://www.w3.org/ns/ttml}span"):
                if span.text:
                    paragraph_text += span.text.strip() + " "

            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                if include_timestamps and "begin" in paragraph.attrib:
                    timestamp = format_timestamp(float(paragraph.attrib["begin"].replace("s", "")))
                    transcript.append(f"[{timestamp}] {paragraph_text}")
                else:
                    transcript.append(paragraph_text)

        return "\n\n".join(transcript)

    except ET.ParseError as e:
        raise ValueError(f"Error parsing TTML file: {e}")


def handler(event, context):
    """Lambda handler for extracting transcript from TTML."""
    try:
        # Get job info from event
        job_id = event['jobId']
        ttml_key = event['ttmlKey']
        
        # Download TTML file from S3
        response = s3_client.get_object(Bucket=STORAGE_BUCKET, Key=ttml_key)
        ttml_content = response['Body'].read().decode('utf-8')
        
        # Extract transcript
        transcript = extract_transcript(ttml_content, include_timestamps=False)
        
        # Save transcript to S3
        transcript_key = f"transcripts/{job_id}.txt"
        s3_client.put_object(
            Bucket=STORAGE_BUCKET,
            Key=transcript_key,
            Body=transcript.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Update job table
        table = dynamodb.Table(JOB_TABLE)
        table.update_item(
            Key={'jobId': job_id},
            UpdateExpression='SET #status = :status, transcriptKey = :transcriptKey, #updated = :updated',
            ExpressionAttributeNames={
                '#status': 'status',
                '#updated': 'updatedAt'
            },
            ExpressionAttributeValues={
                ':status': 'transcript_extracted',
                ':transcriptKey': transcript_key,
                ':updated': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'statusCode': 200,
            'jobId': job_id,
            'transcriptKey': transcript_key
        }
        
    except Exception as e:
        print(f"Error extracting transcript: {str(e)}")
        raise

