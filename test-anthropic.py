import boto3
import json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

model_id = "us.anthropic.claude-opus-4-6-v1"

prompt = "Describe the purpose of a 'hello world' program in one line."

native_request = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 512,
    "temperature": 0.5,
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        }
    ],
}

request = json.dumps(native_request)

response = client.invoke_model_with_response_stream(
    modelId=model_id,
    body=request
)

# Read streaming response
for event in response["body"]:
    chunk = json.loads(event["chunk"]["bytes"])
    
    if "content" in chunk:
        for c in chunk["content"]:
            if c["type"] == "text":
                print(c["text"], end="")