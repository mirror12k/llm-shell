import os
import requests

from llm_shell.util import bold_gold

chatgpt_api_key = os.getenv('CHATGPT_API_KEY')

def send_to_o1(context):
    return send_to_chatgpt_model(context, 'o1-preview')

def send_to_o1mini(context):
    return send_to_chatgpt_model(context, 'o1-mini')

def send_to_gpt4o(context):
    return send_to_chatgpt_model(context, 'gpt-4o')

def send_to_gpt4omini(context):
    return send_to_chatgpt_model(context, 'gpt-4o-mini')

def send_to_gpt4turbo(context):
    return send_to_chatgpt_model(context, 'gpt-4-turbo')

def send_to_gpt4(context):
    return send_to_chatgpt_model(context, 'gpt-4')

def send_to_gpt35turbo(context):
    return send_to_chatgpt_model(context, 'gpt-3.5-turbo')


total_estimated_cost = 0
total_tokens_used = 0

model_prices = {
    'o1-preview': { 'output': 60, 'input': 15 },
    'o1-mini': { 'output': 12, 'input': 3 },
    'gpt-4o': { 'output': 15, 'input': 5 },
    'gpt-4o-mini': { 'output': 0.6, 'input': 0.15 },
    'gpt-4-turbo': { 'output': 30, 'input': 10 },
    'gpt-4': { 'output': 60, 'input': 30 },
    'gpt-3.5-turbo': { 'output': 6, 'input': 3 },
    # 'gpt-4-1106-preview': { 'output': 30, 'input': 10 },
    # 'gpt-3.5-turbo-1106': { 'output': 2, 'input': 1 },
}
def send_to_chatgpt_model(context, model):
    global total_estimated_cost, total_tokens_used, chatgpt_api_key

    if not chatgpt_api_key:
        raise Exception("Can't execute chatgpt without 'CHATGPT_API_KEY' environment variable set.")

    headers = {
        "Authorization": f"Bearer {chatgpt_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": context,
        "temperature": 0.5,
        "max_tokens": 4096
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)


    if response.status_code == 200:
        response_data = response.json()
        # Calculate the estimated cost based on input and output tokens
        estimated_cost_input = response_data['usage']['prompt_tokens'] * model_prices[model]['input'] / 1000000
        estimated_cost_output = response_data['usage']['completion_tokens'] * model_prices[model]['output'] / 1000000
        total_estimated_cost += estimated_cost_input + estimated_cost_output
        total_tokens_used += response_data['usage']['total_tokens']

        # print(f"\t(Total tokens so far: {bold_gold(str(total_tokens_used))}, Total cost so far: {bold_gold(f'${total_estimated_cost:.2f}')} )")

        assistant_message = response_data['choices'][0]['message']['content']
        return assistant_message.strip()
    else:
        return f"Error: {response.status_code}, {response.text}"

# loads a list of openai model ids from the API
def get_openai_models():
    global chatgpt_api_key

    if not chatgpt_api_key:
        raise Exception("Can't execute chatgpt without 'CHATGPT_API_KEY' environment variable set.")

    headers = {
        "Authorization": f"Bearer {chatgpt_api_key}",
        "Content-Type": "application/json"
    }

    response = requests.get("https://api.openai.com/v1/models",  headers=headers)

    response_data = response.json()
    model_ids = list(map(lambda d: d['id'], response_data['data']))

    return model_ids
