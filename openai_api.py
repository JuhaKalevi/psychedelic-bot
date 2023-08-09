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
        "prompt": {
          "type":"string",
          "description":"Convert user image request to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features."
                        " Don't use full sentences, just a few keywords, separating these aspects by commas, or periods which separate bigger units consisting of multiple comma separated keywords together."
                        " Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally, for example breathtaking, award-winning, professional, highly detailed"
                        " Don't use any kind of formatting to separate these keywords, expect commas and periods! Remember to translate everything to english!"
        },
        "negative_prompt": {
          "type":"string",
          "description":"List some features that describe what should NOT be in the generated image, based on what the user wants to see. For example if the user wants a photograph, it should not be drawn or comic style & vice versa."
                        " Also, in most cases people don't want anime, cartoon, graphic, text, painting, crayon, graphite, abstract glitch, blurry looking pictures unless they specifically say so. You can use these as default negative prompts usually!"
                        " Don't use full sentences, just a few keywords, separating these aspects by commas, or periods which separate bigger units consisting of multiple comma separated keywords together."
                        " Don't use any kind of formatting to separate these keywords, expect commas and periods! Remember to translate everything to english!"
        },
        "count": {
          "type":"integer",
          "description":"How many images? 1-8"
        }
      },
      "required": ["prompt","negative_prompt","count"]
    }
  }
]

async def chat_completion(messages:list, model='gpt-4') -> str:
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages)
    return response['choices'][0]['message']['content']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(response_message:str, available_functions:dict) -> str:
  messages=[{"role":"user", "content":response_message}]
  try:
    response = await openai.ChatCompletion.acreate(model='gpt-4-0613', messages=messages, functions=functions)
  except openai_exceptions as err:
    return f"OpenAI API Error: {json.dumps(err)}"
  response_message = response["choices"][0]["message"]
  if response_message.get("function_call"):
    function = json.loads(available_functions[response_message["function_call"]])
    await function["name"](**function["arguments"])
  return response_message

async def chat_completion_streamed(messages:dict, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions as err:
    logger.debug("OpenAI API Error: %s", err)
    return
