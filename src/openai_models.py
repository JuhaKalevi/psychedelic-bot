from json import loads
from openai import AsyncOpenAI
from transformers import pipeline

from helpers import count_tokens
from openai_function_schema import actions, empty_params, semantic_analysis, intention_analysis

async def react(full_context:list, available_functions:dict):
  client = AsyncOpenAI()
  try:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    print(f"zero-shot-classification: {classifier(full_context[-1]['content'], ['self_analysis_request','image_generation_request'])}")
    semantic_analysis_attempts = 0
    while semantic_analysis_attempts < 3:
      semantic_analysis_attempts += 1
      current_context = full_context[-semantic_analysis_attempts:]
      semantics = await think(current_context, semantic_analysis(len(current_context)/len(full_context)), 'gpt-3.5-turbo-1106')
      semantic_analysis_confidence = semantics['confidence_rating']
      if current_context == full_context or semantic_analysis_confidence > 0.85:
        break
    intention = await think([{'role':'user','content':semantics['analysis']}], intention_analysis(list(available_functions)), 'gpt-4-1106-preview')
    action = intention['next_action']
    action_description = next(([f] for f in actions if f['name'] == action), [])
    if action_description[0]['parameters'] != empty_params:
      action_arguments_completion = await client.chat.completions.create(messages=full_context, functions=action_description, function_call={'name':action}, model='gpt-4-1106-preview', temperature=0)
      arguments = loads(action_arguments_completion.choices[0].message.function_call.arguments)
      await available_functions[action](**arguments)
    else:
      await available_functions[action]()
  except IndexError as err:
    print(f'{action}: ERROR: {err}')

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

async def say(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
