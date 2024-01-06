import os
import json



def send_to_claude_instant1(context):
    return send_to_bedrock(context, 'anthropic.claude-instant-v1')

def send_to_claude21(context):
    return send_to_bedrock(context, 'anthropic.claude-v2:1')

role_mapping = {
    'user': 'Human',
    'assistant': 'Assistant',
}

def send_to_bedrock(context, model):
    import boto3

    # Initialize the Bedrock AI client lazily
    bedrock_runtime_client = boto3.client('bedrock-runtime')  

    system_prompt = next(step for step in context if step['role'] == 'system')
    prompt = '\n\n'.join( f"{role_mapping[step['role']]}: {step['content']}" for step in context if step['role'] != 'system' )
    prompt += f"\n\n{system_prompt['content']}"
    prompt += '\n\nAssistant:'

    # Prepare the body of the request
    body = json.dumps({
        "prompt": prompt,
        "max_tokens_to_sample": 300,
        "temperature": 0.5,
        "top_k": 250,
        "top_p": 1,
        "stop_sequences": ["\n\nHuman:"],
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
        response_text = json.loads(response['body'].read())['completion']
        return response_text.strip()
    else:
        return f"Error: {response['ResponseMetadata']['HTTPStatusCode']}, {response}"
