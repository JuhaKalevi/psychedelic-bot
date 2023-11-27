from json import loads
from httpx import Timeout
from openai import AsyncOpenAI
from helpers import count_tokens

IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
empty_params = {'type':'object','properties':{}}
f_detailed = [
  {
    'name': 'text_response_default',
    'description': "This function is called when no other function is called. It's used to provide default text response behavior for the bot. Select this function when another function isn't explicitly called.",
    'parameters': empty_params
  },
  {
    'name': 'analyze_images',
    'description': "Analyze images using a local API. Don't worry if you don't seem to have an image at this stage, the function will find it for you! If the users seems to be refering to an image you can assume it exists.",
    'parameters': {
      'type': 'object',
      'properties': {
        'count': {'type': 'integer','description': "How many previous images to analyze?"}
      }
    }
  },
  {
    'name': 'channel_summary',
    'description': "Summarize previous discussions in a larger context (user calls it channel or discussion or just 'here')",
    'parameters': {
      'type': 'object',
      'properties': {
        'count': {'type': 'integer','description': "How many previous posts to summarize?"}
      },
      'required': ['count']
    }
  },
  {
    'name': 'self_code_analysis',
    'description': "Analyze your source code files that are automatically readable later in this function. Nothing can be provided by the user, this only reads the source code you are currently running.",
    'parameters': empty_params
  },
  {
    'name': 'generate_images',
    'description': "Generate images from the user message using a local API. Don't use this function unless the message specifically asks for it!",
    'parameters': {
      'type': 'object',
      'properties': {
        'prompt': {
          'type': 'string',
          'description':"Convert user image request to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features."
                        f' {IMGGEN_PROMPT} {IMGGEN_GROUPS} {IMGGEN_WEIGHT}'
                        " If the user's request seems to already be in this format, just decide which part should go to the negative_prompt parameter which describes conceptual opposites of the requested image. Then don't use those parts in this parameter!"
                        f' {IMGGEN_REMIND}'
        },
        'negative_prompt': {
          'type': 'string',
          'description':"Convert user image request to english, in such a way that you are describing conceptually opposite features of the picture that is requested in the message, starting from the most strikingly opposite features."
                        f' {IMGGEN_PROMPT} {IMGGEN_GROUPS} {IMGGEN_WEIGHT}'
                        " The negative_prompt is used to describe the conceptual opposites of the requested image, so it can be often crafted by just replacing the most important keywords with their opposites."
                        f' {IMGGEN_REMIND}'
        },
        'count': {'type':'integer'},
        'resolution': {
          'type': 'string',
          'enum': ['1024x1024','1152x896','896x1152','1216x832','832x1216','1344x768','768x1344','1536x640','640x1536'],
          'description': "The resolution of the generated image. The first number is the width, the second number is the height. The resolution is in pixels. Try to translate user requests like 1080p to the closest resolution available."
        },
        'sampling_steps': {'type':'integer'}
      },
      'required': ['prompt']
    }
  },
  {
    'name': 'get_current_weather',
    'description': "Get the current weather in a given location",
    'parameters': {
      'type': 'object',
      'properties': {
        'location': {'type':'string','description': "The city and state, e.g. San Francisco, CA"}
      },
      'required': ['location']
    }
  }
]

client = AsyncOpenAI(timeout=Timeout(180.0, read=10.0, write=10.0, connect=5.0))

async def chat_completion_functions(msgs:list, f_avail:dict):
  f_choose = [
    {
      'name': 'choose_function',
      'description': "This function is used to select which of the actual functions should be called.",
      'parameters': {
        'type': 'object',
        'properties': {
          'function_name': {
            'type': 'string',
            'description': "This parameter decides which function is actually called in the next stage.",
            'enum': list(f_avail),
          }
        },
        'required': ['function_name']
      }
    }
  ]
  f_coarse = []
  for f in [f for f in f_detailed if f['name'] in f_avail.keys()]:
    f_coarse.append({'name':f['name'],'parameters':empty_params})
  print(f'f_coarse: {count_tokens(f_coarse)} tokens')
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=f_choose+f_coarse, function_call={'name':'choose_function'}, model='gpt-3.5-turbo-1106', stream=True):
    print(dict(r.choices[0].delta))
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_choice = loads(delta)['function_name']
      break
  f_description = [f for f in f_detailed if f['name'] == f_choice]
  print(f'f_detailed ({f_choice}): {count_tokens(f_description)} tokens')
  if f_description[0]['parameters'] != empty_params:
    f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
    function_args_msg = f_args_completion.choices[0].message
    arguments = loads(function_args_msg.function_call.arguments)
    await f_avail[f_choice](**arguments)
  else:
    await f_avail[f_choice]()

async def chat_completion_streamed(messages:list, functions=None, model='gpt-4-1106-preview', max_tokens=None):
  kwargs = {"messages":messages, "model":model, "stream":True}
  if functions:
    kwargs["functions"] = functions
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    content = part.choices[0].delta.content or ""
    yield content
