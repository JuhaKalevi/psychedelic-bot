from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens

IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
empty_params = {'type':'object','properties':{}}

f_estimate_required_context = [
  {
    'name': 'estimate_required_context',
    'parameters': {
      'type': 'object',
      'properties': {
        'required_context': {
          'type': 'integer',
          'description': "How many previous posts should be used to decide which function to call? This includes your own posts as well.",
          'enum': [1,2,3,4]
        }
      },
      'required': ['required_context']
    }
  }
]

f_detailed = [
  {
    'name': 'text_response_default',
    'parameters': empty_params
  },
  {
    'name': 'analyze_images_referred_in_message',
    'parameters': {
      'type': 'object',
      'properties': {
        'count_images': {'type': 'integer','description': "How many previous images to analyze?"},
        'count_posts': {'type': 'integer','description': "How many previous posts to analyze?"}
      }
    }
  },
  {
    'name': 'outside_context_lookup',
    'parameters': {
      'type': 'object',
      'properties': {
        'count': {'type': 'integer','description': "How many previous posts to summarize?"}
      },
      'required': ['count']
    }
  },
  {
    'name': 'instant_self_code_analysis',
    'parameters': empty_params
  },
  {
    'name': 'generate_images_requested_in_message',
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

async def chat_completion_choices(msgs:list, f_avail:dict, f_choose:list, decision:str, model:str):
  client = AsyncOpenAI()
  f_coarse = []
  for f in [f for f in f_detailed if f['name'] in f_avail.keys()]:
    f_coarse.append({'name':f['name'],'parameters':empty_params})
  print(f'{decision} tokens:{count_tokens(f_choose+f_coarse)} msgs:{count_tokens(msgs)}')
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=f_choose+f_coarse, function_call={'name':f_choose[0]['name']}, model=model, stream=True):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_decision = loads(delta)[decision]
      print(f'{decision}:{f_decision}')
      return f_decision

async def chat_completion_functions(msgs:list, f_avail:dict):
  client = AsyncOpenAI()
  f_choose = [
    {
      'name': 'choose_function',
      'description': "Select which actual function to call. Rely on text_response_default if uncertain.",
      'parameters': {
        'type': 'object',
        'properties': {
          'function_name': {
            'type': 'string',
            'description': "If there is a question about a function, that is strong indicator NOT to call it, instant_self_code_analysis could be more appropriate then. Only if some other function is explicitly requested to be executed, not merely mentioned, should they be even considered.",
            'enum': list(f_avail)
          }
        },
        'required': ['function_name']
      }
    }
  ]
  f_required_context = await chat_completion_choices(msgs[-1:], {}, f_estimate_required_context, 'required_context', 'gpt-4-1106-preview')
  f_choice = await chat_completion_choices(msgs[-f_required_context:], f_avail, f_choose, 'function_name', 'gpt-4-1106-preview')
  f_description = next(([f] for f in f_detailed if f['name'] == f_choice), [])
  try:
    if f_description[0]['parameters'] != empty_params:
      print(f'{f_choice}:{count_tokens(f_description)} msgs:{count_tokens(msgs)}')
      f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
      function_args_msg = f_args_completion.choices[0].message
      arguments = loads(function_args_msg.function_call.arguments)
      await f_avail[f_choice](**arguments)
    else:
      await f_avail[f_choice]()
  except IndexError as err:
    print(f'{f_choice}:{err}')

async def chat_completion(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':2, 'top_p':0.95}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  print(f'chat_completion: msgs:{count_tokens(msgs)}')
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
