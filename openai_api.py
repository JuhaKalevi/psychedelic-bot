import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

async def chat_completion(messages:list, model='gpt-4') -> str:
  try:
    print(f"TRACE: openai.ChatCompletion.acreate(), len({messages}")
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return str(response['choices'][0]['message']['content'])
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"
