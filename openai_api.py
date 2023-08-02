import json
import os
import openai
import log

logger = log.get_logger(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

functions = [
  {
    "name": "channel_summary",
    "description": "Summarize previous discussions in a larger context (user calls it channel or discussion or just 'here')",
    "parameters": {
      "type": "object",
      "properties": {
        "count": {
          "type":"integer",
          "description":"How many previous posts to summarize?"
        }
      },
      "required": ["count"]
    }
  },
  {
    "name": "code_analysis",
    "description": "Analyze code files that are automatically readable by your function. That's your chatbot code!",
    "parameters": {
      "type": "object",
      "properties": {}
    }
  },
  {
    "name": "generate_images",
    "description": "Generate images from the user message using a local API",
    "parameters": {
      "type": "object",
      "properties": {
        "count": {
          "type":"integer",
          "description":"How many images? 1-8"
        }
      },
      "required": ["count"]
    }
  }
]

async def chat_completion(messages:list, model='gpt-4') -> str:
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return response['choices'][0]['message']['content']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(message:str, available_functions:dict) -> str:
  messages=[{"role":"user", "content":message}]
  try:
    response_message = await openai.ChatCompletion.acreate(model='gpt-3.5-turbo-0613', messages=messages, functions=functions)
  except openai_exceptions as err:
    return f"OpenAI API Error: {json.dumps(err)}"
  response_message = response_message["choices"][0]["message"]
  if response_message.get("function_call"):
    logger.debug(response_message["function_call"])
    function = response_message["function_call"]["name"]
    arguments = json.loads(response_message["function_call"]["arguments"])
    function_response = await available_functions[function](**arguments)
    logger.debug(function_response)
  return response_message

async def chat_completion_streamed(messages:dict, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions as err:
    yield f"OpenAI API Error: {err}"
