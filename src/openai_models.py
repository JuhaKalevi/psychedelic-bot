from json import loads
from openai import AsyncOpenAI
from helpers import is_mainly_english
from openai_function_schema import generate_images_schema

async def chat_completion(kwargs):
  client = AsyncOpenAI()
  async for part in await client.chat.completions.create(**kwargs, stream=True):
    yield part.choices[0].delta
  await client.close()

async def consider(kwargs):
  completion = ''
  print(kwargs)
  async for delta in chat_completion(kwargs):
    if 'function_call' in kwargs:
      if delta.function_call:
        completion += delta.function_call.arguments
      else:
        print(completion)
        return {arg:loads(completion)[arg] for arg in kwargs['functions'][0]['parameters']['properties'] if arg in loads(completion)}
    else:
      if delta.content is not None:
        completion += delta.content
      else:
        print(f'Completion: {completion}')
        return completion

async def react(context:list, available_functions:dict):
  if not is_mainly_english(context[-1]['content']):
    translation_reflection = [
      {'role':'system','content':'You are a NLP processor.'},
      {'role':'user','content':'ONLY translate my messages to ENGLISH SEMANTICS instead of replying normally!'},
      {'role':'assistant','content':'Understood! I will ONLY TRANSLATE your messages to ENGLISH SEMANTICS and do NOTHING ELSE.'},
      context[-1]
    ]
    user_content = {'role':'user','content':await consider({'messages':translation_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0})}
  else:
    user_content = context[-1]
  self_analysis_reflection = [
    {'role':'system','content':'You are a CLASSIFIER that is ONLY allowed to respond with 1 or 0 to DETERMINE if a message calls for INCLUDING YOUR CHATBOT SOURCE CODE into the context before answering.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting analysis of YOUR chatbot capabilities! Reply 1 if the message is requesting analysis of your capabilities, and 0 if it is not!'},
    {'role':'assistant','content':'Understood! I will ONLY answer 1 or 0 to your messages, signifying if they are requesting analysis of MY capabilities. I will NEVER reply anything else!'},
    user_content,
    {'role':'user','content':'PLEASE REMEMBER TO ONLY REPLY 1 or 0'}
  ]
  image_generation_reflection = [
    {'role':'system','content':'You are a CLASSIFIER that is ONLY allowed to respond with 1 or 0 to DETERMINE if a message calls for the generation of images using a local API.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting image generation!'},
    {'role':'assistant','content':'Understood! I will ONLY answer 1 or 0 to your messages, signifying if they are requesting images. I will NEVER reply anything else!'},
    user_content,
    {'role':'user','content':'PLEASE REMEMBER TO ONLY REPLY 1 or 0'}
  ]
  if await consider({'messages':self_analysis_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    await available_functions['analyze_self']()
  elif await consider({'messages':image_generation_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    await available_functions['generate_images'](**await consider({'messages':context, 'functions':[generate_images_schema], 'function_call':{'name':'generate_images'}, 'model':'gpt-4-1106-preview'}))
  else:
    await available_functions['Chat']()
