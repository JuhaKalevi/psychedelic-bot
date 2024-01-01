from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from openai_function_schema import ACTIONS

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

async def background_function(kwargs):
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

async def chat_completion(kwargs):
  client = AsyncOpenAI()
  async for part in await client.chat.completions.create(**kwargs, stream=True):
    yield part.choices[0].delta

def classify(message, labels):
  if len(labels) > 1:
    classification = classifier(message, labels)
    return dict(zip(classification['labels'], classification['scores']))
  return classifier(message, labels[0])['scores'][0]

async def react(context:list, available_functions:dict):
  action = 'Chat'
  translation = await background_function({'messages':[{'role':'system','content':'Just translate this message to english instead of replying normally'}, context[-1]], 'model':'gpt-3.5-turbo-1106', 'temperature':0})
  meaning = await background_function({'messages':[{'role':'user','content':f'ONLY describe the meaning of the rest of this message INSTEAD OF REPLYING NORMALLY:\n{translation}'}], 'model':'gpt-3.5-turbo-1106', 'temperature':0})
  if classify(meaning, ['Analysis of code, functions or capabilities.']) > 0.6:
    print('CONSIDER analyze_self')
    if classify(meaning, ['Message refers to you.']) > 0.6:
      print('DO analyze_self')
      action = 'analyze_self'
  else:
    if classify(meaning, ['Instructions that describe an image the user wants to generate.']) > 0.8:
      print('DO generate_images')
      action = 'generate_images'
    elif classify(meaning, ['Confirmation of image generation request.']) > 0.8:
      print('DO generate_images')
      action = 'generate_images'
  action_arguments = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_arguments:
    await available_functions[action](**await background_function({'messages':context, 'functions':action_arguments, 'function_call':{'name':action}, 'model':'gpt-4-1106-preview'}))
  else:
    await available_functions[action]()
