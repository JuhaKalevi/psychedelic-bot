from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens, is_mostly_english
from openai_function_schema import text_response_default, estimate_required_context, generate_images, runtime_self_analysis, empty_params

async def chat_completion_choices(msgs:list, f_avail:dict, f_choose:list, decisions:list[str], model:str):
  client = AsyncOpenAI()
  f_coarse = []
  f_stage = f_choose[0]['name']
  for f in [f for f in text_response_default+runtime_self_analysis+generate_images if f['name'] in f_avail.keys()]:
    f_coarse.append({'name':f['name'],'parameters':empty_params})
  print(f"{f_stage}:{count_tokens(f_choose+f_coarse+msgs)}")
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=f_choose+f_coarse, function_call={'name':f_stage}, model=model, stream=True):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_decision = {d:loads(delta)[d] for d in decisions}
      print(f"{f_stage}:{f_decision}")
      return f_decision

async def chat_completion_functions(msgs:list, f_avail:dict):
  print(f"is_mostly_english:{is_mostly_english(msgs[-1]['content'])}")
  client = AsyncOpenAI()
  try:
    f_required_context = await chat_completion_choices(msgs[-1:], {}, estimate_required_context, ['modality','posts'], 'gpt-4-1106-preview')
    if f_required_context['modality'] == 'image' and f_required_context['posts'] == 0:
      f_required_context['posts'] = 1
    if int(f_required_context['posts']):
      if f_required_context['modality'] == 'image':
        f_avail = {f: f_avail[f] for f in f_avail if f in [fdict['name'] for fdict in text_response_default]}
      elif f_required_context['modality'] == 'self':
        f_avail = {f: f_avail[f] for f in f_avail if f in [fdict['name'] for fdict in runtime_self_analysis]}
      elif f_required_context['modality'] == 'text':
        f_avail = {f: f_avail[f] for f in f_avail if f in [fdict['name'] for fdict in text_response_default]}
      f_choose = [
        {
          'name': 'choose_function',
          'parameters': {
            'type': 'object',
            'properties': {
              'function_name': {
                'type': 'string',
                'enum': list(f_avail)
              }
            },
            'required': ['function_name']
          }
        }
      ]
      f_choice = await chat_completion_choices(msgs[-int(f_required_context['posts']):], f_avail, f_choose, ['function_name'], 'gpt-4-1106-preview')
      f_choice = f_choice['function_name']
      if f_required_context['modality'] == 'image':
        f_description = next(([f] for f in generate_images+text_response_default if f['name'] == f_choice), [])
      elif f_required_context['modality'] == 'self':
        f_description = next(([f] for f in runtime_self_analysis if f['name'] == f_choice), [])
      elif f_required_context['modality'] == 'text':
        f_description = next(([f] for f in text_response_default if f['name'] == f_choice), [])
      if f_description[0]['parameters'] != empty_params:
        print(f'{f_choice}:{count_tokens(f_description)} msgs:{count_tokens(msgs)}')
        f_args_completion = await client.chat.completions.create(messages=msgs, functions=f_description, function_call={'name':f_choice}, model='gpt-4-1106-preview')
        function_args_msg = f_args_completion.choices[0].message
        arguments = loads(function_args_msg.function_call.arguments)
        await f_avail[f_choice](**arguments)
      else:
        await f_avail[f_choice]()
    else:
      await f_avail['text_response_default']()
  except IndexError as err:
    print(f'{f_choice}: ERROR: {err}')

async def chat_completion(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
