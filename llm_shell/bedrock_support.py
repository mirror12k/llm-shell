import os
import json



def send_to_claude_instant1(context):
    return send_to_bedrock(context, 'anthropic.claude-instant-v1')

def send_to_claude21(context):
    return send_to_bedrock(context, 'anthropic.claude-v2:1')

def send_to_claude3sonnet(context):
    return send_to_bedrock(context, 'anthropic.claude-3-sonnet-20240229-v1:0')

def send_to_claude35sonnet(context):
    return send_to_bedrock(context, 'anthropic.claude-3-5-sonnet-20240620-v1:0')

def send_to_claude3haiku(context):
    return send_to_bedrock(context, 'anthropic.claude-3-haiku-20240307-v1:0')

def send_to_claude3opus(context):
    return send_to_bedrock(context, 'anthropic.claude-3-opus-20240229-v1:0')

role_mapping = {
    'user': 'Human',
    'assistant': 'Assistant',
}

def merge_sequential_messages(messages):
    merged = []
    prev_role = None
    current = {}

    for msg in messages:
        if msg['role'] != prev_role:
            if current:
                merged.append(current)
            current = msg.copy()
            prev_role = msg['role']
        else:
            current['content'] += '\n\n\n' + msg['content']

    if current:
        merged.append(current)

    return merged


def send_to_bedrock(context, model):
    import boto3

    # Initialize the Bedrock AI client lazily
    bedrock_runtime_client = boto3.client('bedrock-runtime')  

    system_prompt = next(step['content'] for step in context if step['role'] == 'system')
    context_prompts = [ step for step in context if step['role'] != 'system' ]
    context_prompts = merge_sequential_messages(context_prompts)

    # Prepare the body of the request
    body = json.dumps({
        "messages": [ { "role": step['role'], "content": [{
                    "type": "text",
                    "text": step['content']
                }] } for step in context_prompts ],
        "system": system_prompt,
        "max_tokens": 30000,
        "temperature": 0.5,
        "top_k": 250,
        "top_p": 1,
        # "stop_sequences": ["\n\nHuman:"],
        "anthropic_version": "bedrock-2023-05-31"
    })

    # Call the Bedrock AI model
    response = bedrock_runtime_client.invoke_model(
        body=body,
        modelId=model,
        accept='*/*',
        contentType='application/json'
    )


    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        response_body = json.loads(response['body'].read())
        # print(response_body)
        response_text = response_body['content'][0]['text']
        return response_text.strip()
    else:
        return f"Error: {response['ResponseMetadata']['HTTPStatusCode']}, {response}"
