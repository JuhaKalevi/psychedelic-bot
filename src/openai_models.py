from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens
from openai_function_schema import generate_images_schema

async def chat_completion(kwargs):
  if kwargs['model'] == 'gpt-3.5-turbo-instruct':
    async for part in await AsyncOpenAI().completions.create(**kwargs, stream=True):
      print(part.choices[0].text)
      yield part.choices[0].text
  else:
    async for part in await AsyncOpenAI().chat.completions.create(**kwargs, stream=True):
      yield part.choices[0].delta

async def consider(kwargs):
  completion = ''
  async for delta in chat_completion(kwargs):
    if 'function_call' in kwargs:
      if delta.function_call:
        completion += delta.function_call.arguments
      else:
        print(completion)
        return {arg:loads(completion)[arg] for arg in kwargs['functions'][0]['parameters']['properties'] if arg in loads(completion)}
    else:
      if kwargs['model'] == 'gpt-3.5-turbo-instruct':
        buffer = delta
      else:
        buffer = delta.content
      if buffer is not None:
        completion += buffer
      else:
        print(f'Completion: {completion}')
        return completion

async def react(context:list, available_functions:dict):
  if len(context) < 3:
    print('SINGLE MESSAGE')
    translation = f'Reply with the following message translated to english if necessary. Just repeat the message if translation is not necessary. Message begins: {context[-1]["content"]}'
  else:
    translation = f'Reply with the following two messages translated to english if necessary. Just repeat the messages if translation is not necessary. Messages begin: {context[-2]["content"]} {context[-1]["content"]}'
  semantics = await consider({'prompt':translation, 'model':'gpt-3.5-turbo-instruct', 'max_tokens':4000-count_tokens(translation)})
  self_analysis_reflection = [
    {'role':'system','content':'You are a CLASSIFIER that is ONLY allowed to respond with 1 or 0 to DETERMINE if a message calls for INCLUDING YOUR CHATBOT SOURCE CODE into the context before answering.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting analysis of YOUR chatbot capabilities! Reply 1 if the message is requesting analysis of your capabilities, and 0 if it is not!'},
    {'role':'assistant','content':'Understood! I will ONLY answer 1 or 0 to your messages, signifying if they are requesting analysis of MY capabilities. I will NEVER reply anything else!'},
    {'role':'user','content':semantics},
    {'role':'user','content':'PLEASE REMEMBER TO ONLY REPLY 1 or 0'}
  ]
  image_generation_reflection = [
    {'role':'system','content':'You are a CLASSIFIER that is ONLY allowed to respond with 1 or 0 to DETERMINE if a message calls for the generation of images using a local API.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting image generation!'},
    {'role':'assistant','content':'Understood! I will ONLY answer 1 or 0 to your messages, signifying if they are requesting images. I will NEVER reply anything else!'},
    {'role':'user','content':semantics},
    {'role':'user','content':'PLEASE REMEMBER TO ONLY REPLY 1 or 0'}
  ]
  if await consider({'messages':self_analysis_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    await available_functions['analyze_self']()
  elif await consider({'messages':image_generation_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    await available_functions['generate_images'](**await consider({'messages':context, 'functions':[generate_images_schema], 'function_call':{'name':'generate_images'}, 'model':'gpt-4-1106-preview'}))
  else:
    await available_functions['Chat']()
