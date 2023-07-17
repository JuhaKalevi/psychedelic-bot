import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

async def openai_chat_completion(messages, model='gpt-4'):
  try:
    print('openai_chat_completion')
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content is not None:
        print(content, end='')
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"
