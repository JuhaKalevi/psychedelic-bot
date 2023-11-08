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
                        " Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!"
                        " Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
                        " If the user's request seems to already be in this format, just decide which part should go to the negative_prompt parameter which describes conceptual opposites of the requested image. Then don't use those parts in this parameter!"
                        " Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
        },
        "negative_prompt": {
          "type":"string",
          "description":"Convert user image request to english, in such a way that you are describing conceptually opposite features of the picture that is requested in the message, starting from the most strikingly opposite features."
                        " Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
                        " Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together."
                        " It's important to place the most important elements first in all of these levels of groupings!"
                        " Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!"
                        " Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
                        " The negative_prompt is used to describe the conceptual opposites of the requested image, so it can be often crafted by just replacing the most important keywords with their opposites."
                        " Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
        },
        "count": {
          "type":"integer",
        },
        "resolution": {
          "type":"string",
          "enum":["1024x1024","1152x896","896x1152","1216x832","832x1216","1344x768","768x1344","1536x640","640x1536"],
          "description":"The resolution of the generated image. The first number is the width, the second number is the height. The resolution is in pixels. Try to translate user requests like 1080p to the closest resolution available."
        },
        "sampling_steps": {
          "type":"integer"
        }
      },
      "required": ["prompt"]
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
        "desired_changes": {
          "type": "string"
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
        "english_proficiency": {
          "type": "string"
        }
      }
    }
  },
  {
    "name": "upscale_image",
    "description": "Upscale an image using a local API",
    "parameters": {
      "type": "object",
      "properties": {
        "scale": {
          "type": "number"
        }
      }
    }
  }
]

openai.api_key = environ['OPENAI_API_KEY']
openai_exceptions = (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.ServiceUnavailableError, openai.error.Timeout)

async def chat_completion(messages:list, functions=None):
  try:
    response = await openai.ChatCompletion.acreate(model=choose_model(messages), messages=messages, functions=functions)
    return response['choices'][0]['message']
  except openai_exceptions as err:
    return f"OpenAI API Error: {err}"

async def chat_completion_functions(messages:list, available_functions:dict):
  response_message = await chat_completion(messages, functions=function_descriptions)
  if response_message.get("function_call"):
    function = response_message["function_call"]["name"]
    arguments = loads(response_message["function_call"]["arguments"])
    await available_functions[function](**arguments)
  return response_message

async def chat_completion_streamed(messages:list, functions=None):
  try:
    kwargs = {"model": choose_model(messages), "messages": messages, "stream": True}
    if functions:
      kwargs["functions"] = functions
    async for chunk in await openai.ChatCompletion.acreate(**kwargs):
      content = chunk["choices"][0].get("delta", {}).get("content")
      if content:
        yield content
  except openai_exceptions:
    return

def choose_model(msgs:list) -> str:
  tokens = count_tokens(msgs)
  if tokens < 12288:
    model = 'gpt-3.5-turbo-1106'
  elif tokens < 126976:
    model = 'gpt-4-1106-preview'
  else:
    model = ''
  print(f'{model}: {tokens}')
  return model

def count_tokens(msg:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(dumps(msg)))

async def generate_story_from_captions(msg:str):
  return await chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {msg}")}], 'gpt-4')

async def generate_summary_from_transcription(msg:str):
  return await chat_completion([{
    'role': 'user',
    'content': (
      f"Summarize in appropriate detail, adjusting the summary length according to the transcription's length, the YouTube-video transcription below. IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s), etc. completely!"
      f" Also make a guess on how many different characters' speech is included in the transcription."
      f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
      f" Also give scoring 0-10 about the video for each of these categories: originality, difficulty, humor, boringness, creativity, artful."
      f" Transcription: {msg}"
    )
  }], 'gpt-4')

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
