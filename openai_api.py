import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

async def chat_completion(messages, model='gpt-4'):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    response_content = response['choices'][0]['message']['content']
    return str(response_content)
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_streamed(messages, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions as err:
    yield f"OpenAI API Error: {err}"
