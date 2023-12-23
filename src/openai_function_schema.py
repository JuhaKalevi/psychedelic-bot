# Schema variables for functions that are exposed to user

EMPTY_PARAMS = {'type':'object','properties':{}}

IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"

actions = [
  {
    'name': 'analyze_self',
    'description': "Read your own code temporarily into the context in order to analyze it. This is NOT a background task! This can be used to analyze other functions.",
    'parameters': EMPTY_PARAMS
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
          'description': "Resolution of generated image. First number is width, second number is height. Try to translate user requests like 1080p or portrait/landscape to the closest resolution available."
        },
        'sampling_steps': {'type':'integer'}
      },
      'required': ['prompt']
    }
  }
]

# Methods for internal use only, not exposed to user

def double_check(event_classifications):
  return {
    'name': 'double_check',
    'description': f"Double check these zero-shot-classifications: {[f for f in event_classifications if event_classifications[f] > 0.5]}",
    'parameters': {
      'type': 'object',
      'properties': {
        'confidence': {
          'type': 'number',
          'description': "Your confidence for these classifications against the message.",
          'minimum': 0,
          'maximum': 1
        },
      },
      'required': ['confidence']
    }
  }

def in_english():
  return {
    'name': 'double_check',
    'description': f"Double check these zero-shot-classifications: {[f for f in event_classifications if event_classifications[f] > 0.5]}",
    'parameters': {
      'type': 'object',
      'properties': {
        'confidence': {
          'type': 'number',
          'description': "Your confidence for these classifications against the message.",
          'minimum': 0,
          'maximum': 1
        },
      },
      'required': ['confidence']
    }
  }
