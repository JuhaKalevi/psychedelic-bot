import json
import os
import openai
import log

logger = log.get_logger(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

functions = [
  {
    "name": "generate_images",
    "description": "Generate images from the user message using a local API",
    "parameters": {
      "type": "object",
      "properties": {
        "count":{
          "type":"integer",
          "description":"How many images? 1-8"
        },
      },
      "required": ["count"]
    }
  }
]

async def chat_completion(messages, model='gpt-4'):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return response['choices'][0]['message']['content']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(message, available_functions):
  messages=[{"role":"user", "content":message}]
  try:
    response = await openai.ChatCompletion.acreate(model='gpt-3.5-turbo-0613', messages=messages, functions=functions)
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"
  response_message = response["choices"][0]["message"]
  logger.debug(response_message)
  if response_message.get("function_call"):
    function_name = response_message["function_call"]["name"]
    function_response = await available_functions[function_name](*json.loads(response_message["function_call"]["arguments"]))
    messages.append(response_message)
    messages.append({"role": "function", "name":function_name, "content":function_response})
    return await chat_completion(messages, 'gpt-3-5-turbo-0613')

async def chat_completion_streamed(messages, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions as err:
    yield f"OpenAI API Error: {err}"
