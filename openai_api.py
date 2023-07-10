from os import environ
import openai

openai.api_key = environ['OPENAI_API_KEY']

async def openai_chat_completion(messages:list, model='gpt-4') -> str:
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return str(response['choices'][0]['message']['content'])
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"
