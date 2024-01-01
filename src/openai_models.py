from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from openai_function_schema import translate_to_english, ACTIONS, EMPTY_PARAMS

event_labels = {
 'code_analysis':'Analysis of code, functions or capabilities.',
}
action_labels = {
  'analyze_self':'Message refers to you.',
  'generate_images':'Instructions that describe an image the user wants to generate.',
}
confirmation_labels = {
  'generate_images':'Confirmation of image generation request.'
}
zero_shot_classification_pipeline = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

async def background_function(kwargs):
  completion = ''
  async for delta in chat_completion(kwargs):
    if delta.function_call:
      completion += delta.function_call.arguments
    else:
      print(completion)
      return {d:loads(completion)[d] for d in kwargs['functions'][0]['parameters']['properties'] if d in loads(completion)}

async def chat_completion(kwargs):
  client = AsyncOpenAI()
  async for part in await client.chat.completions.create(**kwargs, stream=True):
    yield part.choices[0].delta

def classify(event_translation, labels):
  zero_shot_classifications_object = zero_shot_classification_pipeline(event_translation, labels)
  scores = dict(zip(zero_shot_classifications_object['labels'], zero_shot_classifications_object['scores']))
  print(scores)
  return scores

async def react(context:list, available_functions:dict):
  action = 'Chat'
  last_message_in_english = await background_function({'messages':[{'role':'system','content':'Just translate this message to english instead of replying normally'},context[-1]], 'model':'gpt-3.5-turbo-instruct'})
  event_translation = f"System message:\n{context[0]['content']}\n\nInteractions:\n{last_message_in_english['translation']}"
  if classify(event_translation, list(event_labels.values()))[event_labels['code_analysis']] > 0.6:
    if classify(event_translation, [e for e in action_labels.values() if e == action_labels['analyze_self']])[action_labels['analyze_self']] > 0.8:
      action = 'analyze_self'
  else:
    if classify(event_translation, [e for e in action_labels.values() if e == action_labels['generate_images']])[action_labels['generate_images']] > 0.8:
      action = 'generate_images'
    elif classify(event_translation, [e for e in confirmation_labels.values() if e == confirmation_labels['generate_images']])[confirmation_labels['generate_images']] > 0.8:
      action = 'generate_images'
  action_description = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
    await available_functions[action](**await background_function({'messages':context, 'functions':action_description, 'function_call':{'name':action}, 'model':'gpt-4-1106-preview', 'temperature':0}))
  else:
    await available_functions[action]()
