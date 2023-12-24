from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from helpers import count_tokens
from openai_function_schema import ANALYZE_SELF, GENERATE_IMAGES, translate_to_english, actions, EMPTY_PARAMS

EVENT_CATEGORIES = ['Instructions given to the chatbot to perform a specific action.', 'Inquiries seeking information or explanations on a variety of topics.', 'Messages that address the chatbot directly or discuss its functions, capabilities, or status.']

async def chat(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""

def select_labels(classifications, threshold, always_include=None):
  return {label: score for label, score in classifications.items() if score > threshold or label in (always_include or [])}

async def classify(event_translation, full_context, labels=None):
  print(event_translation)
  if not labels:
    labels = EVENT_CATEGORIES
  zero_shot_classifications_object = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")(event_translation, labels, multi_label=True)
  event_classifications = dict(zip(zero_shot_classifications_object['labels'], zero_shot_classifications_object['scores']))
  print(event_classifications)
  if zero_shot_classifications_object['labels'][0] == 'Chat':
    action = await classify(event_translation, full_context, labels=[ANALYZE_SELF, GENERATE_IMAGES, 'Chat'])
  elif zero_shot_classifications_object['labels'][0] == 'Question':
    action = await classify(event_translation, full_context, labels=[ANALYZE_SELF, 'Chat'])
  else:
    action = 'Chat'
  print(action)
  return action

async def react(full_context:list, available_functions:dict):
  client = AsyncOpenAI()
  action = 'Chat'
  if full_context[0] in full_context[-3:]:
    context = full_context[-3:]
  else:
    context = full_context[:1] + full_context[-3:]
  print(context[1:])
  context_interactions_in_english = await think(context[1:], translate_to_english(), 'gpt-3.5-turbo-1106')
  print(context_interactions_in_english)
  event_translation = f"System message:\n{full_context[0]['content']}\n\nInteractions:\n{context_interactions_in_english['translation']}"
  action = await classify(event_translation, full_context)
  #print(await think(context, double_check(event_classifications), 'gpt-3.5-turbo-1106'))
  action_description = next(([f] for f in actions if f['name'] == action), [])
  if action != 'Chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
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
