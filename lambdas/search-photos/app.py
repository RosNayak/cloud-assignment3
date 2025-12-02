import json
import os
import requests
import boto3
import uuid

ES_ENDPOINT = "https://search-photos-depdjgmiqpar2bs54q5rehyg3u.aos.us-east-1.on.aws"      # e.g. https://photos-xxxx.es.amazonaws.com
ES_INDEX = "photos"
ES_USERNAME = "roshu21"
ES_PASSWORD = "Nayak4@27!"
PHOTO_BUCKET = 'roshan-assignment3-b2'

# Lex V2 runtime config – set these as Lambda environment variables
LEX_BOT_ID = "9AOHOXSVCE"         # e.g. "ABCD1234..."
LEX_BOT_ALIAS_ID = "TSTALIASID"  # e.g. "TSTALIASID"
LEX_LOCALE_ID = "en_GB"

lex_client = boto3.client("lexv2-runtime")
s3 = boto3.client("s3")

# def extract_keywords_from_lex_event(event):
#     """
#     Get the user's search terms from the Lex event.
#     We try to use a slot called 'Keyword', fall back to inputTranscript.
#     """
#     slots = event.get('currentIntent', {}).get('slots', {}) or {}
#     text = slots.get('Keyword') or event.get('inputTranscript') or ""
#     # Very simple keyword extraction: lowercase, split on spaces, remove empties
#     words = [w.strip() for w in text.replace(",", " ").split() if w.strip()]
#     return words

# def extract_keywords_from_lex_event(event: str):
#     if not isinstance(event, str):
#         return []

#     text = event.strip()
#     if not text:
#         return []

#     words = [w.strip() for w in text.replace(",", " ").split() if w.strip()]
#     return words

def extract_keywords_from_lex_event(text: str):
    """
    Send the user's free-text query to Lex and let Lex parse it.
    We then pull out the 'Keyword' slot if present; otherwise
    we fall back to Lex's interpreted text.
    """
    if not text:
        return []

    # Call Lex V2 Runtime
    response = lex_client.recognize_text(
        botId=LEX_BOT_ID,
        botAliasId=LEX_BOT_ALIAS_ID,
        localeId=LEX_LOCALE_ID,
        sessionId=str(uuid.uuid4()),
        text=text,
    )

    # Example structure:
    # response["sessionState"]["intent"]["slots"]["Keyword"]["value"]["interpretedValue"]
    intent = response.get("sessionState", {}).get("intent", {}) or {}
    slots = intent.get("slots") or {}

    slot_value = None
    kw_slot = slots.get("Keyword")
    if kw_slot and kw_slot.get("value"):
        slot_value = kw_slot["value"].get("interpretedValue")

    # Fallback: use Lex's interpreted text if slot not present
    if not slot_value:
        slot_value = response.get("inputTranscript") or text

    # Very simple keyword tokenization
    words = [w.strip() for w in slot_value.replace(",", " ").split() if w.strip()]
    return words


def search_photos_by_labels(keywords):
    """
    Query OpenSearch 'photos' index for documents whose labels contain the given keywords.
    We use a bool/should + terms query on labels.keyword.
    """
    if not keywords:
        return []

    # Build an OR query across the labels.keyword field
    should_clauses = [
        {"term": {"labels.keyword": kw}} for kw in keywords
    ]

    body = {
        "size": 10,  # return up to 10 matches
        "query": {
            "bool": {
                "should": should_clauses,
                "minimum_should_match": 1
            }
        }
    }

    url = f"{ES_ENDPOINT}/{ES_INDEX}/_search"
    resp = requests.get(url,
                        auth=(ES_USERNAME, ES_PASSWORD),
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(body),
                        timeout=5)

    if resp.status_code not in (200, 201):
        print("Error from ES:", resp.status_code, resp.text)
        return []

    hits = resp.json().get("hits", {}).get("hits", [])
    results = []
    for h in hits:
        src = h.get("_source", {})
        results.append({
            "objectKey": src.get("objectKey"),
            "bucket": src.get("bucket"),
            "labels": src.get("labels", [])
        })
    return results


def build_lex_response(intent_name: str, fulfillment_state: str, message_text: str):
    """
    Build a Lex V2-compatible response.
    """
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "name": intent_name,
                "state": fulfillment_state
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message_text
            }
        ]
    }

def lambda_handler(event, context):
    print("Lex event:", json.dumps(event))

    qs = event.get("queryStringParameters") or {}
    print("Query string parameters:", qs)
    q = qs.get("q", "")

    # keywords = extract_keywords_from_lex_event(event)
    keywords = extract_keywords_from_lex_event(q)
    print("Extracted keywords:", keywords)

    if not keywords:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": f"I didn't find any keywords in your request. {q}"
        }

    results = search_photos_by_labels(keywords)
    print("Search results:", json.dumps(results))

    # if not results:
    #     return build_lex_response(
    #         intent_name,
    #         "Fulfilled",
    #         "I couldn't find any photos matching your query."
    #     )

    if not results:
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": "I couldn't find any photos matching your query."
        }

    output = []
    s3 = boto3.client('s3')
    for r in results:
        key = r['objectKey']
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': PHOTO_BUCKET, 'Key': key},
            ExpiresIn=3600   # 1 hour
        )
        output.append({
            'bucket': PHOTO_BUCKET,
            'objectKey': key,
            'presigned_url': url
        })

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"results": output})
    }
    # lines = []
    # for r in results:
    #     s3_uri = f"s3://{r['bucket']}/{r['objectKey']}"
    #     lines.append(f"- {s3_uri} (labels: {', '.join(r['labels'])})")

    # message = "Here are some matching photos:\n" + "\n".join(lines)

    # return build_lex_response(intent_name, "Fulfilled", message)
