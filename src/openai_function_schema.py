
IMGGEN_PROMPT = "Don't use full sentences, just a few keywords, separating these aspects by spaces or commas so that each comma separated group can have multiple space separated keywords."
IMGGEN_GROUPS = "Instead of commas, it's possible to use periods which separate bigger units consisting of multiple comma separated keywords or groups of keywords together. It's important to place the most important elements first in all of these levels of groupings!"
IMGGEN_WEIGHT = "Parentheses are used to increase the weight of (emphasize) tokens, such as: (((red hair))). Each set of parentheses multiplies the weight by 1.05. Convert adjectives like 'barely', 'slightly', 'very' or 'extremely' to this format!. Curly brackets can be conversely used to de-emphasize with a similar logic & multiplier."
IMGGEN_REMIND = "Don't use any kind of formatting to separate these keywords, expect what is mentioned above! Remember to translate everything to english!"
empty_params = {'type':'object','properties':{}}

def translate_to_english():
  return {
    'name': 'translate_to_english',
    'parameters': {
      'type': 'object',
      'properties': {
        'translation': {'type': 'string'}
      },
      'required': ['translation']
    }
  }

def semantic_analysis(recalled_context_fraction):
  return {
    'name': 'semantic_analysis',
    'description': f"Provide ONLY a concise semantic analysis of the message, DO NOT actually answer like you normally would! Think and think again, could the message be unclear due to context being partially missing? You currently see {round(recalled_context_fraction*100)}% of the context.",
    'parameters': {
      'type': 'object',
      'properties': {
        'analysis': {
          'type': 'string',
        },
        'confidence_rating': {
          'type': 'number',
          'description': "Confidence rating (0-1) on how certain you are about this analysis.",
        }
      },
      'required': ['analysis','confidence_rating']
    }
  }

def intention_analysis(available_functions):
  return {
    'name': 'intention_analysis',
    'parameters': {
      'type': 'object',
      'properties': {
        'confidence_rating': {
          'type': 'number',
          'description': "Confidence rating (0-1) on how certain you are what to do next given provided actions.",
        },
        'next_action': {
          'type': 'string',
          'enum': available_functions
        }
      },
      'required': ['confidence_rating','next_action']
    }
  }

actions = [
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
  },
  {
    'name': 'runtime_self_analysis',
    'description': "Read your own code temporarily into the context in order to analyze it. This is NOT a background task! This can be used to analyze other functions.",
    'parameters': empty_params
  },
  {
    'name': 'text_response_default',
    'description': 'Default function that can be called when a normal text response suffices, or when the user requests a function that is not available or seems inappropriate.',
    'parameters': empty_params
  }
]
