from json import loads
from openai import AsyncOpenAI
from transformers import pipeline
from openai_function_schema import translate_to_english, ACTIONS, EMPTY_PARAMS

event_categories = {
  'analyze_self':'Messages that address the chatbot directly for developing its functions & capabilities.',
  'generate_images':'Instructions given to the chatbot to generate/display described images, when not discussing the chatbot itself.'
}

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

async def react(full_context:list, available_functions:dict):
  action = 'Chat'
  if full_context[0] in full_context[-3:]:
    context = full_context[-3:]
  else:
    context = full_context[:1] + full_context[-3:]
  context_interactions_in_english = await background_function({'messages':context[1:], 'functions':[translate_to_english], 'function_call':{'name':translate_to_english['name']}, 'model':'gpt-4-1106-preview'})
  event_translation = f"System message:\n{full_context[0]['content']}\n\nInteractions:\n{context_interactions_in_english['translation']}"
  zero_shot_classifications_object = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")(event_translation, list(event_categories.values()))
  event_classifications = dict(zip(zero_shot_classifications_object['labels'], zero_shot_classifications_object['scores']))
  print(event_classifications)
  if event_classifications[event_categories['analyze_self']] > 0.8 and event_classifications[event_categories['generate_images']] < 0.2:
    action = 'analyze_self'
  elif event_classifications[event_categories['generate_images']] > 0.8 and event_classifications[event_categories['analyze_self']] < 0.2:
    action = 'generate_images'
  action_description = next(([f] for f in ACTIONS if f['name'] == action), [])
  if action != 'Chat' and action_description[0]['parameters'] != EMPTY_PARAMS:
    await available_functions[action](**await background_function({'messages':full_context, 'functions':action_description, 'function_call':{'name':action}, 'model':'gpt-4-1106-preview', 'temperature':0}))
  else:
    await available_functions[action]()
