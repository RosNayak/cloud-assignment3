import json
import os
import requests

ES_ENDPOINT = "https://search-photos-depdjgmiqpar2bs54q5rehyg3u.aos.us-east-1.on.aws"      # e.g. https://photos-xxxx.es.amazonaws.com
ES_INDEX = "photos"
ES_USERNAME = "roshu21"
ES_PASSWORD = "Nayak4@27!"


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

def extract_keywords_from_lex_event(event: str):
    if not isinstance(event, str):
        return []

    text = event.strip()
    if not text:
        return []

    words = [w.strip() for w in text.replace(",", " ").split() if w.strip()]
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

    # intent = event.get("sessionState", {}).get("intent", {}) or {}
    # intent_name = intent.get("name", "SearchIntent")

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

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"results": results})
    }
    # lines = []
    # for r in results:
    #     s3_uri = f"s3://{r['bucket']}/{r['objectKey']}"
    #     lines.append(f"- {s3_uri} (labels: {', '.join(r['labels'])})")

    # message = "Here are some matching photos:\n" + "\n".join(lines)

    # return build_lex_response(intent_name, "Fulfilled", message)
