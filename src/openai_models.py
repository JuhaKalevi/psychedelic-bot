from json import loads
from openai import AsyncOpenAI
from openai_function_schema import ACTIONS

async def chat_completion(kwargs):
  client = AsyncOpenAI()
  async for part in await client.chat.completions.create(**kwargs, stream=True):
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
      if delta.content is not None:
        completion += delta.content
      else:
        print(f'Completion: {completion}')
        return completion

async def react(context:list, available_functions:dict):
  translation_reflection = [
    {'role':'system','content':'You are a translator.'},
    {'role':'user','content':'ONLY translate my messages to english instead of replying normally'},
    {'role':'assistant','content':'Understood! I will only translate your messages to english and do nothing else.'},
    {'role':'user','content':context[-1]}
  ]
  translation = await consider({'messages':translation_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0})
  self_analysis_reflection = [
    {'role':'system','content':'You are a validator for true/false questions.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting analysis of YOUR chatbot capabilities.'},
    {'role':'assistant','content':'Understood! I will only answer 1 or 0 to your messages, signifying if they are requesting analysis of MY capabilities.'},
    {'role':'user','content':translation}
  ]
  image_generation_reflection = [
    {'role':'system','content':'You are a validator for true/false questions.'},
    {'role':'user','content':'From now on ONLY classify whether messages are requesting image generation.'},
    {'role':'assistant','content':'Understood! I will only answer 1 or 0 to your messages, signifying if they are requesting image generation.'},
    {'role':'user','content':translation}
  ]
  action = 'Chat'
  if await consider({'messages':self_analysis_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    action = 'analyze_self'
  elif await consider({'messages':image_generation_reflection, 'model':'gpt-3.5-turbo-1106', 'temperature':0, 'max_tokens':1}) == '1':
    action = 'generate_images'
  action_arguments = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_arguments:
    await available_functions[action](**await consider({'messages':context, 'functions':action_arguments, 'function_call':{'name':action}, 'model':'gpt-4-1106-preview'}))
  else:
    await available_functions[action]()
