from os import environ
from openai import api_key, ChatCompletion
from openai.error import APIConnectionError, APIError, AuthenticationError, InvalidRequestError, PermissionError, RateLimitError, ServiceUnavailableError, Timeout

api_key = environ['OPENAI_API_KEY']

async def openai_chat_completion(messages, model=environ['OPENAI_MODEL_NAME']):
  try:
    openai_response_content = await ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (APIConnectionError, APIError, AuthenticationError, InvalidRequestError, PermissionError, RateLimitError, ServiceUnavailableError, Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content
