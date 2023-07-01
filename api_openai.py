import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

async def openai_chat_completion(messages, model=os.environ['OPENAI_MODEL_NAME']):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return response['choices'][0]['message']['content']
  except (openai.error.APIConnectionError,
          openai.error.APIError,
          openai.error.AuthenticationError,
          openai.error.InvalidRequestError,
          openai.error.PermissionError,
          openai.error.RateLimitError,
          openai.error.ServiceUnavailableError,
          openai.error.Timeout) as err:
    return f"OpenAI API Error: {err}"
