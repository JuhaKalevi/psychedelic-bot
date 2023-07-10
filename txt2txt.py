import json
import os
import requests
import bot
import openai_api
import tiktoken
import txt2bool

async def choose_system_message(post:dict, analyze_code:bool=False) -> list:
  default_system_message = [{'role':'system', 'content':'You are an assistant with no specific role determined right now.'}]
  if not analyze_code:
    analyze_code = await txt2bool.is_asking_for_code_analysis(post)
  if analyze_code:
    code_snippets = []
    for file_path in [x for x in os.listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGIN {file_path} ---\n{code}\n')
    default_system_message = [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  return bot._return(default_system_message)

async def count_tokens(message:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def fix_image_generation_prompt(prompt:str) -> str:
  fixed_prompt = await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")
  return bot._return(fixed_prompt)

async def generate_story_from_captions(message:dict, model='gpt-4') -> str:
  story = await openai_api.chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)
  return story

async def generate_text_from_context(context:dict, model='gpt-4') -> str:
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]])
  context_messages = []
  context_tokens = await count_tokens(context)
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role': role, 'content': context['posts'][post_id]['message']}
    message_tokens = await count_tokens(message)
    if context_tokens + message_tokens < 7777:
      context_messages.append(message)
      context_tokens += message_tokens
    else:
      break
  if os.environ['LOG_LEVEL'] == 'Trace':
    print(f'TRACE: context_tokens: {context_tokens}')
  context_messages.reverse()
  openai_response = await openai_api.openai_chat_completion(system_message + context_messages, model)
  return bot._return(openai_response)

async def generate_text_from_message(message:dict, model='gpt-4') -> str:
  response = await openai_api.openai_chat_completion([{'role': 'user', 'content': message}], model)
  return bot._return(response)

async def textgen_chat_completion(user_input:str, history) -> str:
  request = {
    'user_input': user_input,
    'max_new_tokens': 1200,
    'history': history,
    'mode': 'instruct',
    'character': 'Example',
    'instruction_template': 'WizardLM',
    'your_name': 'You',
    'regenerate': False,
    '_continue': False,
    'stop_at_newline': False,
    'chat_generation_attempts': 1,
    'chat-instruct_command': 'Continue the chat dialogue below. Write a lengthy step-by-step answer for the character "<|character|>".\n\n<|prompt|>',
    'preset': 'None',
    'do_sample': True,
    'temperature': 0.7,
    'top_p': 0.1,
    'typical_p': 1,
    'epsilon_cutoff': 0,  # In units of 1e-4
    'eta_cutoff': 0,  # In units of 1e-4
    'tfs': 1,
    'top_a': 0,
    'repetition_penalty': 1.18,
    'repetition_penalty_range': 0,
    'top_k': 40,
    'min_length': 0,
    'no_repeat_ngram_size': 0,
    'num_beams': 1,
    'penalty_alpha': 0,
    'length_penalty': 1,
    'early_stopping': False,
    'mirostat_mode': 0,
    'mirostat_tau': 5,
    'mirostat_eta': 0.1,
    'seed': -1,
    'add_bos_token': True,
    'truncation_length': 2048,
    'ban_eos_token': False,
    'skip_special_tokens': True,
    'stopping_strings': []
  }
  response = requests.post(os.environ['TEXTGEN_WEBUI_URI'], json=request, timeout=420)
  if response.status_code == 200:
    response_content = json.loads(response.text)
    results = response_content["results"]
    for result in results:
      chat_history = result.get("history", {})
      internal_history = chat_history.get("internal", [])
      if internal_history:
        last_entry = internal_history[-1]
        if len(last_entry) > 1:
          answer = last_entry[1]
          return answer
  return 'oops'
