from json import dumps, loads
from os import environ
import requests
import openai.error
import tiktoken

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
                        " Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
                        " Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together."
                        " It's important to place the most important elements first in all of these levels of groupings!"
                        " Keyword can also have a colon and a number after it, for example 'cat:1.5' means that the user wants cats with weight 1.5 in the picture."
                        " If this weighing is used for a keyword group that has multiple members, the group should have parentheses around it in the prompt, for example 'cat:3, dog:2, (horse, cow):1.1'"
                        " Where the user doesn't specify weight numbers, it's assumed to be 1 and mustn't be explicitly added. 1.5 is already quite a lot more, 0 is none."
                        " If the user's request seems to already be in this format, just pass the prompt without modifications."
                        " Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
        },
        "count": {
          "type":"integer",
          "enum":[1,2,3,4,5,6,7,8,9,10]
        },
        "resolution": {
          "type":"string",
          "enum":["1024x1024","1152x896","896x1152","1216x832","832x1216","1344x768","768x1344","1536x640","640x1536"],
          "description":"The resolution of the generated image. The first number is the width, the second number is the height. The resolution is in pixels. Try to translate user requests like 1080p to the closest resolution available."
        }
      },
      "required": ["prompt","count"]
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
  },
  {
    "name": "instruct_pix2pix",
    "description": "Slightly alter an image using a local API",
    "parameters": {
      "type": "object",
      "properties": {
        "scale": {
          "type": "number",
        }
      }
    }
  },
  {
    "name": "store_user_preferences",
    "description": "Store user preferences in a local database",
    "parameters": {
      "type": "object",
      "properties": {
        "english proficiency": {
          "type": "string",
        }
      }
    }
  },
  {
    "name": "upscale_image",
    "description": "Upscale an image using a local API",
    "parameters": {}
  }
]

openai.api_key = environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

async def chat_completion(messages:list, model='gpt-4', functions=None):
  try:
    response = await openai.ChatCompletion.acreate(model=model, messages=messages, functions=functions)
    return response['choices'][0]['message']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(messages:list, available_functions:dict):
  response_message:dict = await chat_completion(messages, model='gpt-4-0613', functions=function_descriptions)
  if response_message.get("function_call"):
    function = response_message["function_call"]["name"]
    arguments = loads(response_message["function_call"]["arguments"])
    await available_functions[function](**arguments)
  return response_message

async def chat_completion_streamed(messages:list, model='gpt-4'):
  try:
    async for chunk in await openai.ChatCompletion.acreate(model=model, messages=messages, stream=True):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions:
    return

def count_tokens(msg:str):
  return len(tiktoken.get_encoding('cl100k_base').encode(dumps(msg)))

async def generate_story_from_captions(msg:str, model='gpt-4'):
  return await chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {msg}")}], model)

async def generate_summary_from_transcription(msg:str, model='gpt-4'):
  return await chat_completion([{
    'role': 'user',
    'content': (
      f"Summarize in appropriate detail, adjusting the summary length according to the transcription's length, the YouTube-video transcription below. IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s), etc. completely!"
      f" Also make a guess on how many different characters' speech is included in the transcription."
      f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
      f" Also give scoring 0-10 about the video for each of these categories: originality, difficulty, humor, boringness, creativity, artful."
      f" Transcription: {msg}"
    )
  }], model)

async def textgen_chat_completion(message:str, history:dict) -> str:
  request = {
    'user_input': message,
    'max_new_tokens': 1200,
    'history': history,
    'mode': 'instruct',
    'character': 'Example',
    'instruction_template': 'WizardLM',
    'your_name': 'You',
    'regenerate': False,
    '_continue': False,
    'stop_at_newline': False,
    'chat_generation_attempts': 1,
    'chat-instruct_command': 'Continue the chat dialogue below. Write a lengthy step-by-step answer for the character "<|character|>".\n\n<|prompt|>',
    'preset': 'None',
    'do_sample': True,
    'temperature': 0.7,
    'top_p': 0.1,
    'typical_p': 1,
    'epsilon_cutoff': 0,  # In units of 1e-4
    'eta_cutoff': 0,  # In units of 1e-4
    'tfs': 1,
    'top_a': 0,
    'repetition_penalty': 1.18,
    'repetition_penalty_range': 0,
    'top_k': 40,
    'min_length': 0,
    'no_repeat_ngram_size': 0,
    'num_beams': 1,
    'penalty_alpha': 0,
    'length_penalty': 1,
    'early_stopping': False,
    'mirostat_mode': 0,
    'mirostat_tau': 5,
    'mirostat_eta': 0.1,
    'seed': -1,
    'add_bos_token': True,
    'truncation_length': 2048,
    'ban_eos_token': False,
    'skip_special_tokens': True,
    'stopping_strings': []
  }
  response = requests.post(environ['TEXTGEN_WEBUI_URI'], json=request, timeout=420)
  if response.status_code == 200:
    response_content = loads(response.text)
    results = response_content["results"]
    for result in results:
      chat_history = result.get("history", {})
      internal_history = chat_history.get("internal", [])
      if internal_history:
        last_entry = internal_history[-1]
        if len(last_entry) > 1:
          answer = last_entry[1]
          return answer
  return 'oops'
