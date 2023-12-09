from json import loads
from openai import AsyncOpenAI
from helpers import count_tokens
from openai_function_schema import f_default, f_estimate_required_context, f_img, f_txt, empty_params

async def chat_completion_choices(msgs:list, f_avail:dict, f_choose:list, decisions:list[str], model:str):
  client = AsyncOpenAI()
  f_coarse = []
  f_stage = f_choose[0]['name']
  for f in [f for f in f_default+f_txt+f_img if f['name'] in f_avail.keys()]:
    f_coarse.append({'name':f['name'],'parameters':empty_params})
  print(f"{f_stage}:{count_tokens(f_choose+f_coarse+msgs)}")
  delta = ''
  async for r in await client.chat.completions.create(messages=msgs, functions=f_choose+f_coarse, function_call={'name':f_stage}, model=model, stream=True, temperature=0.5, top_p=0.5):
    if r.choices[0].delta.function_call:
      delta += r.choices[0].delta.function_call.arguments
    else:
      f_decision = {d:loads(delta)[d] for d in decisions}
      print(f"{f_stage}:{f_decision}")
      return f_decision

async def chat_completion_functions(msgs:list, f_avail:dict):
  client = AsyncOpenAI()
  f_choose = [
    {
      'name': 'choose_function',
      'parameters': {
        'type': 'object',
        'properties': {
          'function_name': {
            'type': 'string',
            'description': "Image functions must be explicitly requested to be executed!",
            'enum': list(f_avail)
          }
        },
        'required': ['function_name']
      }
    }
  ]
  try:
    f_required_context = await chat_completion_choices(msgs[-1:], {}, f_estimate_required_context, ['modality','posts'], 'gpt-4-1106-preview')
    if int(f_required_context['posts']):
      if f_required_context['modality'] == 'img':
        f_avail = {f: f_avail[f] for f in f_avail if f in [fdict['name'] for fdict in f_img+f_default]}
      elif f_required_context['modality'] == 'txt':
        f_avail = {f: f_avail[f] for f in f_avail if f in [fdict['name'] for fdict in f_default+f_txt]}
      f_choice = await chat_completion_choices(msgs[-int(f_required_context['posts']):], f_avail, f_choose, ['function_name'], 'gpt-3.5-turbo-16k')
      f_choice = f_choice['function_name']
      if f_required_context['modality'] == 'img':
        f_description = next(([f] for f in f_img+f_default if f['name'] == f_choice), [])
      elif f_required_context['modality'] == 'txt':
        f_description = next(([f] for f in f_default+f_txt if f['name'] == f_choice), [])
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
    print(f'{f_choice}:{err}')

async def chat_completion(msgs, model='gpt-4-1106-preview', max_tokens=None):
  client = AsyncOpenAI()
  kwargs = {'messages':msgs, 'model':model, 'stream':True, 'temperature':0.5, 'top_p':0.5}
  if max_tokens:
    kwargs["max_tokens"] = max_tokens
  print(f'chat_completion: msgs:{count_tokens(msgs)}')
  async for part in await client.chat.completions.create(**kwargs):
    yield part.choices[0].delta.content or ""
