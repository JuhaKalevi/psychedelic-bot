import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

async def openai_chat_completion(messages, model='gpt-4'):
  try:
    print(f"OpenAI Chat Completion Request: {messages}")
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    response_content = response['choices'][0]['message']['content']
    print(f"OpenAI Chat Completion Response: {response_content}")
    return str(response_content)
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"
