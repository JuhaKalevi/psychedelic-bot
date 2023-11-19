from json import loads
from openai import APIError, AsyncOpenAI

IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
empty_params = {'type':'object','properties':{}}
f_detailed = [
  {
    'name': 'no_function',
    'description': "This function is called when no other function is called. It's used to provide default text response behavior for the bot. Select this function when another function isn't explicitly called.",
    'parameters': empty_params
  },
  {
    'name': 'analyze_images',
    'description': "Analyze images using a local API. Don't worry if you don't seem to have an image at this stage, the function will find it for you! If the users seems to be refering to an image you can assume it exists.",
    'parameters': empty_params
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
    'name': 'code_analysis',
    'description': "Analyze your source code files that are automatically readable later in this function. Nothing can be provided by the user, this only reads the source code you are currently running.",
    'parameters': empty_params
  },
  {
    'name': 'generate_images',
    'description': "Generate images from the user message using a local API. Dont't use this function unless the message specifically asks for it!",
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
  },
  {
    'name': 'google_for_answers',
    'description': "Search Google with fully-formed http URL to enhance knowledge.",
    'parameters': {
      'type': 'object',
      'properties': {
        'url': {'type':'string'}
      }
    }
  }
]

client = AsyncOpenAI()

async def chat_completion_functions(msgs:list, f_avail:dict):
  f_coarse = [
    {
      'name': 'choose_function',
      'description': 'This function is the first stage of function call logic. More detailed description of the chosen function is given in the next stage. Possible responses are the names of the functions that are actually available to be called.',
      'parameters': {
        'type': 'object',
        'properties': {
          'chosen_function': {
            'type':'string',
            'enum': [f['name'] for f in f_detailed if f['name'] in f_avail.keys()]
          }
        },
        'required': ['chosen_function']
      }
    }
  ]
  try:
    f_choice_completion = await client.chat.completions.create(messages=msgs, functions=f_coarse, function_call={'name':'choose_function'}, model='gpt-4-1106-preview')
  except APIError as err:
    print(f"OpenAI API Error: {err}")
  f_choice_msg = f_choice_completion.choices[0].message
  f_choice = loads(f_choice_msg.function_call.arguments)['chosen_function']
  print(f"Chosen function: {f_choice}")
  f_description = [f for f in f_detailed if f['name'] == f_choice]
  if f_description[0]['parameters'] != empty_params:
    try:
      f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
    except APIError as err:
      print(f"OpenAI API Error: {err}")
    function_args_msg = f_args_completion.choices[0].message
    arguments = loads(function_args_msg.function_call.arguments)
    await f_avail[f_choice](**arguments)
  else:
    await f_avail[f_choice]()

async def chat_completion_streamed(messages:list, functions=None, model='gpt-4-1106-preview', max_tokens=None):
  try:
    kwargs = {"messages":messages, "model":model, "stream":True}
    if functions:
      kwargs["functions"] = functions
    if max_tokens:
      kwargs["max_tokens"] = max_tokens
    async for part in await client.chat.completions.create(**kwargs):
      content = part.choices[0].delta.content or ""
      yield content
  except APIError as err:
    print(f"OpenAI API Error: {err}")
