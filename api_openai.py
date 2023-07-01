import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

async def openai_chat_completion(messages, model=os.environ['OPENAI_MODEL_NAME']):
  try:
    openai_response_content = await openai.ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError,
          openai.error.APIError,
          openai.error.AuthenticationError,
          openai.error.InvalidRequestError,
          openai.error.PermissionError,
          openai.error.RateLimitError,
          openai.error.ServiceUnavailableError,
          openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content
