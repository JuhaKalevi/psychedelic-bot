from json import loads
from openai import APIError, AsyncOpenAI

function_descriptions = [
  {
    "name":"analyze_images",
    "description":"Analyze images using a local API",
    "parameters": {
      "type": "object",
      "properties": {}
    }
  },
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

client = AsyncOpenAI()

async def chat_completion_functions(messages:list, available_functions:dict):
  try:
    completion = await client.chat.completions.create(messages=messages, functions=function_descriptions, model='gpt-4-1106-preview')
    response_message = completion.choices[0].message
    print(response_message)
    if dict(completion).get("function_call"):
      function = response_message["function_call"]["name"]
      arguments = loads(response_message["function_call"]["arguments"])
      await available_functions[function](**arguments)
    return dict(response_message)
  except APIError as err:
    print(f"OpenAI API Error: {err}")

async def chat_completion_streamed(messages:list, functions=None, model='gpt-4-1106-preview'):
  try:
    kwargs = {"messages":messages, "model":model, "stream":True}
    if functions:
      kwargs["functions"] = functions
    async for part in await client.chat.completions.create(**kwargs):
      content = part.choices[0].delta.content or ""
      yield content
  except APIError as err:
    print(f"OpenAI API Error: {err}")
