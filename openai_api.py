import json
import os
import openai
import log
import mattermost_api

bot = mattermost_api.bot
logger = log.get_logger(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

function_descriptions = [
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
        },
        "resolution": {
          "type":"string",
          "description":"Resolution for requested image."
                        " Default resolution is 1024x1024, and it has to be in this format even if the user describes it in a different way, for example 1080p translates to 1920x1080."
                        " It's also possible to just describe shape of the image, and it should also be translated to the standard format using 1024x1024 as the starting point. The aspect ratio can be anything but the amount of pixels should always be 1048576."
                        " If no resolution is specified, consider what the user wants to see, and use the most common resolution for that type of image."
        }
      },
      "required": ["prompt","negative_prompt","count"]
    }
  },
  {
    "name": "get_current_weather",
    "description": "Get the current weather in a given location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "The city and state, e.g. San Francisco, CA"
        }
      },
      "required": ["location"]
    }
  },
  {
    "name": "google_for_answers",
    "description": "Search Google with fully-formed http URL to enhance knowledge.",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {
          "type": "string",
        }
      }
    }
  }
]
instructions = {'role':'system', 'content':'You are a chatbot part of a larger system that leverages various AI capalibities from OpenAI & others.'
                ' In essence, you have the feature to generate images, as such a function is described in function call descriptions.'
                ' Answer all questions with humour level 100% writing like Gandalf the Grey, and you will be fine.'}

async def chat_completion(messages:list, model='gpt-4', functions=None):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages, functions=functions)
    return response['choices'][0]['message']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(message:str, available_functions:dict):
  response_message = await chat_completion([{"role":"user", "content":message}], model='gpt-4-0613', functions=function_descriptions)
  if response_message.get("function_call"):
    function = response_message["function_call"]["name"]
    arguments = json.loads(response_message["function_call"]["arguments"])
    result = await available_functions[function](**arguments)
    logger.debug('chat_completion_functions() result: %s', result)
  return response_message

async def chat_completion_functions_stage2(post:dict, function:str, arguments:dict, result:dict):
  logger.debug('chat_completion_functions_stage2() function: %s, arguments: %s, result: %s', function, arguments, result)
  messages = [
    {"role": "user", "content": post['message']},
    {"role": "assistant", "content": None, "function_call": {"name": function, "arguments": json.dumps(arguments)}},
    {"role": "function", "name": function, "content": json.dumps(result)}
  ]
  final_result = await chat_completion(messages, model='gpt-4-0613', functions=function_descriptions)
  logger.debug('chat_completion_functions_stage2() final_result: %s', final_result)
  await bot.create_or_update_post({'channel_id':post['channel_id'], 'message':final_result['content'], 'file_ids':None, 'root_id':''})

async def chat_completion_streamed(messages:dict, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=instructions+messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions as err:
    logger.debug("OpenAI API Error: %s", err)
    return
