from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from helpers import count_tokens
from openai_function_schema import actions, EMPTY_PARAMS

ANALYZE_SELF = 'self_code_analysis_request'
GENERATE_IMAGES = 'image_generation_request'
EVENT_CATEGORIES = [ANALYZE_SELF,GENERATE_IMAGES,'affirmation','statement','question','command','greeting','farewell','apology','thanks','other']

async def react(full_context:list, available_functions:dict):
  client = AsyncOpenAI()
  action = 'chat'
  event_classifications_object = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")(full_context[-1]['content'], EVENT_CATEGORIES, multi_label=True)
  event_classifications = dict(zip(event_classifications_object['labels'], event_classifications_object['scores']))
  print(f"event_classifications:{event_classifications}")
  if event_classifications_object['labels'][0] == GENERATE_IMAGES:
    if event_classifications[GENERATE_IMAGES] > event_classifications[ANALYZE_SELF]*1.1:
      action = 'generate_images'
  elif event_classifications_object['labels'][0] == ANALYZE_SELF:
    if event_classifications[ANALYZE_SELF] > event_classifications[GENERATE_IMAGES]*1.1:
      action = 'analyze_self'
  action_description = next(([f] for f in actions if f['name'] == action), [])
  if action != 'chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
    action_arguments_completion = await client.chat.completions.create(messages=full_context, functions=action_description, function_call={'name':action}, model='gpt-4-1106-preview', temperature=0)
    arguments = loads(action_arguments_completion.choices[0].message.function_call.arguments)
    await available_functions[action](**arguments)
  else:
    await available_functions[action]()

async def think(msgs:list, function_call:dict, model:str):
  client = AsyncOpenAI()
  decisions = list(function_call['parameters']['properties'])
  print(f"{function_call['name']}:{count_tokens([function_call]+msgs)}")
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=[function_call], function_call={'name':function_call['name']}, model=model, stream=True):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      outcomes = {d:loads(delta)[d] for d in decisions}
      print(f"{function_call['name']}:{outcomes}")
      return outcomes

async def chat(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
