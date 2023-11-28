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
    'parameters': empty_params
  },
  {
    'name': 'analyze_images',
    'parameters': {
      'type': 'object',
      'properties': {
        'count': {'type': 'integer','description': "How many previous images to analyze?"}
      }
    }
  },
  {
    'name': 'channel_summary',
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
    'parameters': empty_params
  },
  {
    'name': 'generate_images',
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
            'enum': [f for f in list(f_avail) if f != 'choose_function'],
          }
        },
        'required': ['function_name']
      }
    }
  ]
  f_coarse = []
  for f in [f for f in f_detailed if f['name'] in f_avail.keys()]:
    f_coarse.append({'name':f['name'],'parameters':empty_params})
  print(f'f_choose:{count_tokens(f_choose+f_coarse)} msgs:{count_tokens(msgs)}')
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=f_choose+f_coarse, function_call={'name':'choose_function'}, model='gpt-3.5-turbo-16k', stream=True):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_choice = loads(delta)['function_name']
      break
  f_description = [f for f in f_detailed if f['name'] == f_choice]
  if f_description[0]['parameters'] != empty_params:
    print(f'{f_choice}:{count_tokens(f_description)} msgs:{count_tokens(msgs)}')
    f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
    function_args_msg = f_args_completion.choices[0].message
    arguments = loads(function_args_msg.function_call.arguments)
    await f_avail[f_choice](**arguments)
  else:
    await f_avail[f_choice]()

async def chat_completion(msgs, model='gpt-4-1106-preview', max_tokens=None):
  kwargs = {"messages":msgs, "model":model, "stream":True}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  print(f'chat_completion: msgs:{count_tokens(msgs)}')
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
