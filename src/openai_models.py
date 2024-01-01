from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens
from openai_function_schema import generate_images_schema

async def chat_completion(kwargs):
  async for part in await AsyncOpenAI().chat.completions.create(**kwargs, stream=True):
    yield part.choices[0].delta

async def consider(kwargs):
  completion = ''
  print(kwargs)
  if kwargs['model'] == 'gpt-3.5-turbo-instruct':
    completion = await AsyncOpenAI().completions.create(**kwargs)
    return completion.choices[0].text
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
  if len(context) < 3:
    semantics_prompt = f'Convey in english the semantic meaning of the following message:\n\n{context[-1]}'
  else:
    semantics_prompt = f'Convey in english the semantic meaning of the following conversation flow:\n\nPrevious message:{context[-2]}\n\nCurrent message:{context[-1]}'
  semantics = await consider({'prompt':semantics_prompt, 'model':'gpt-3.5-turbo-instruct', 'temperature':0, 'max_tokens':4096-count_tokens(semantics_prompt)})
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
