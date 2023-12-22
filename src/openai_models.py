from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens, is_mostly_english
from openai_function_schema import actions, empty_params, semantic_analysis, intention_analysis

async def understand_intention(msgs:list, function_call:dict, model:str):
  client = AsyncOpenAI()
  decisions = list(function_call['parameters']['properties'])
  print(f"{function_call['name']}:{count_tokens([function_call]+msgs)}")
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=[function_call], function_call={'name':function_call['name']}, model=model, stream=True):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_decision = {d:loads(delta)[d] for d in decisions}
      print(f"{function_call['name']}:{f_decision}")
      return f_decision

async def answer(msgs:list, available_functions:dict):
  print(f"is_mostly_english:{is_mostly_english(msgs[-1]['content'])}")
  client = AsyncOpenAI()
  try:
    semantics = await understand_intention(msgs[-1:], semantic_analysis(), 'gpt-4-1106-preview')
    intention = await understand_intention(semantics['analysis'], intention_analysis(list(available_functions)), 'gpt-3.5-turbo-16k')
    print(intention)
    f_choice = intention['next_action']
    f_description = next(([f] for f in actions if f['name'] == f_choice), [])
    if f_description[0]['parameters'] != empty_params:
      print(f'{f_choice}:{count_tokens(f_description)} msgs:{count_tokens(msgs)}')
      f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
      function_args_msg = f_args_completion.choices[0].message
      arguments = loads(function_args_msg.function_call.arguments)
      await available_functions[f_choice](**arguments)
    else:
      await available_functions[f_choice]()
  except IndexError as err:
    print(f'{f_choice}: ERROR: {err}')

async def chat_completion(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
