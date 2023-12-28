from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from openai_function_schema import translate_to_english, ACTIONS, EMPTY_PARAMS

EVENT_CATEGORIES = ['Instructions given to the chatbot to (often implicitly) generate described images.', 'Messages that address the chatbot directly or discuss its functions, capabilities, or status.']

async def background_function(kwargs):
  completion = ''
  async for delta in chat_completion(kwargs):
    if delta.function_call:
      completion += delta.function_call.arguments
    else:
      print(completion)
      return {d:loads(completion)[d] for d in list(kwargs['functions'][0]['parameters']['properties'])}

async def chat_completion(kwargs):
  client = AsyncOpenAI()
  async for part in await client.chat.completions.create(**kwargs, stream=True):
    yield part.choices[0].delta

async def classify(event_translation, labels=None):
  print(event_translation)
  if not labels:
    labels = EVENT_CATEGORIES
  zero_shot_classifications_object = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")(event_translation, labels, multi_label=True)
  event_classifications = dict(zip(zero_shot_classifications_object['labels'], zero_shot_classifications_object['scores']))
  print(event_classifications)
  action = 'Chat'
  print(action)
  return action

async def react(full_context:list, available_functions:dict):
  action = 'Chat'
  if full_context[0] in full_context[-3:]:
    context = full_context[-3:]
  else:
    context = full_context[:1] + full_context[-3:]
  print(context[1:])
  context_interactions_in_english = await background_function({'messages':context[1:], 'functions':[translate_to_english], 'function_call':{'name':translate_to_english['name']}, 'model':'gpt-4-1106-preview'})
  print(context_interactions_in_english)
  event_translation = f"System message:\n{full_context[0]['content']}\n\nInteractions:\n{context_interactions_in_english['translation']}"
  action = await classify(event_translation)
  action_description = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
    arguments_completion_kwargs = await background_function({'messages':full_context, 'functions':[action_description], 'function_call':{'name':action}, 'model':'gpt-4-1106-preview', 'temperature':0})
    arguments = loads(arguments_completion_kwargs.choices[0].message.function_call.arguments)
    await available_functions[action](**arguments)
  else:
    await available_functions[action]()
