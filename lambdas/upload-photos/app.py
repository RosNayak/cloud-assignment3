import json
import os
import boto3
import urllib.parse
import requests
from datetime import datetime

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')

ES_ENDPOINT = "https://search-photos-depdjgmiqpar2bs54q5rehyg3u.aos.us-east-1.on.aws"      # e.g. https://photos-xxxx.es.amazonaws.com
ES_INDEX = "photos"
ES_USERNAME = "roshu21"
ES_PASSWORD = "Nayak4@27!"

def lambda_handler(event, context):
    # 1. Parse S3 event (assume single record)
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])

    print(f"Indexing object s3://{bucket}/{key}")

    # 2. Call Rekognition DetectLabels
    rek_resp = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=10,
        MinConfidence=70
    )
    rek_labels = [lbl['Name'] for lbl in rek_resp['Labels']]
    print("Rekognition labels:", rek_labels)

    # 3. Get S3 object metadata (for custom labels)
    head = s3.head_object(Bucket=bucket, Key=key)
    user_meta = head.get('Metadata', {})
    custom_labels_str = user_meta.get('customlabels') or user_meta.get('x-amz-meta-customlabels')
    custom_labels = []

    if custom_labels_str:
        # could be comma-separated, adjust to your upload convention
        custom_labels = [l.strip() for l in custom_labels_str.split(',') if l.strip()]

    # A1: full labels array
    labels = list(set(rek_labels + custom_labels))

    # 4. Build JSON document for OpenSearch index
    doc = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": datetime.utcnow().isoformat() + "Z",
        "labels": labels
    }

    # 5. Index document into ES/OpenSearch
    es_url = f"{ES_ENDPOINT}/{ES_INDEX}/_doc"
    headers = {"Content-Type": "application/json"}

    print("About to send document to ES:", es_url)

    try:
        resp = requests.post(
            es_url,
            auth=(ES_USERNAME, ES_PASSWORD),  # <<--- BASIC AUTH HERE
            headers=headers,
            data=json.dumps(doc),
            timeout=5
        )
        print("ES response code:", resp.status_code)
        print("ES response body:", resp.text)
    except Exception as e:
        print("Error calling ES:", repr(e))

    return {"statusCode": 200, "body": "Indexed"}
