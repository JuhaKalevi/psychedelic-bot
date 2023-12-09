
IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
empty_params = {'type':'object','properties':{}}

f_default = [{'name': 'text_response_default','parameters': empty_params}]

f_estimate_required_context = [
  {
    'name': 'estimate_required_context',
    'parameters': {
      'type': 'object',
      'properties': {
        'modality': {
          'type': 'string',
          'enum': ['txt','img'],
        },
        'posts': {
          'type': 'integer',
          'description': "See more posts (including your own previous replies) to decide next action. Use 0 if asked about functions or no explicit action requested! For affirmations or negations use at least 1, and consider otherwise vague messages as 2 or more.",
          'enum': [0,1,2,3,4]
        }
      },
      'required': ['modality','posts']
    }
  }
]

f_img = [
  {
    'name': 'analyze_images_referred',
    'parameters': {
      'type': 'object',
      'properties': {
        'count_images': {'type': 'integer','description': "How many previous images to analyze?"},
        'count_posts': {'type': 'integer','description': "How many previous posts to analyze?"}
      }
    }
  },
  {
    'name': 'generate_images_requested',
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
  }
]

f_txt = [
  {
    'name': 'get_current_weather',
    'parameters': {
      'type': 'object',
      'properties': {
        'location': {'type':'string','description': "The city and state, e.g. San Francisco, CA"}
      },
      'required': ['location']
    }
  },
  {
    'name': 'instant_self_code_analysis',
    'description': "Read your own code temporarily into the context in order to analyze it.",
    'parameters': empty_params
  },
  {
    'name': 'outside_context_lookup_summary',
    'parameters': {
      'type': 'object',
      'properties': {
        'count': {'type': 'integer','description': "How many previous posts to summarize?"}
      },
      'required': ['count']
    }
  }
]
