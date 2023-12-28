from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from openai_function_schema import translate_to_english, ACTIONS, EMPTY_PARAMS

event_labels = {
 'code_analysis':'Request for analysis of your code, features, functions or capabilities.',
}
action_labels = {
  'analyze_self':'Addressing questions or ideas about your development or state of the project.',
  'generate_images':'Instructions that describe an image the user wants to generate.',
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

async def react(full_context:list, available_functions:dict):
  action = 'Chat'
  if full_context[0] in full_context[-3:]:
    context = full_context[-3:]
  else:
    context = full_context[:1] + full_context[-3:]
  context_interactions_in_english = await background_function({'messages':context[1:], 'functions':[translate_to_english], 'function_call':{'name':translate_to_english['name']}, 'model':'gpt-4-1106-preview'})
  event_translation = f"System message:\n{full_context[0]['content']}\n\nInteractions:\n{context_interactions_in_english['translation']}"
  if classify(event_translation, list(event_labels.values()))[event_labels['code_analysis']] > 0.6:
    if classify(event_translation, [e for e in action_labels.values() if e == action_labels['analyze_self']])[action_labels['analyze_self']] > 0.8:
      action = 'analyze_self'
  elif classify(event_translation, [e for e in action_labels.values() if e == action_labels['generate_images']])[action_labels['generate_images']] > 0.8:
    action = 'generate_images'
  action_description = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
    await available_functions[action](**await background_function({'messages':full_context, 'functions':action_description, 'function_call':{'name':action}, 'model':'gpt-4-1106-preview', 'temperature':0}))
  else:
    await available_functions[action]()
