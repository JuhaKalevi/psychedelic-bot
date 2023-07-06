import os
import json
import chardet
import langdetect
import tiktoken
from api_mattermost import mm
from api_openai import openai_chat_completion

async def choose_system_message(post):
  if await is_asking_for_code_analysis(post['message']):
    code_snippets = []
    for file_path in [x for x in os.listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGING {file_path} ---\n{code}\n')
    return[{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  else:
    return []

def count_tokens(message):
  encoding = tiktoken.get_encoding('cl100k_base')
  return len(encoding.encode(json.dumps(message)))

async def generate_text_from_context(context):
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(mm.channels.get_channel(context['posts'][context['order'][0]]))
  context_messages = []
  context_tokens = count_tokens(context)
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role': role, 'content': context['posts'][post_id]['message']}
    message_tokens = count_tokens(message)
    if context_tokens + message_tokens < 7777:
      context_messages.append(message)
      context_tokens += message_tokens
    else:
      break
  context_messages.reverse()
  response = await openai_chat_completion(system_message + context_messages, os.environ['OPENAI_MODEL_NAME'])
  return response

async def generate_text_from_message(message, model='gpt-4'):
  response = await openai_chat_completion([{'role': 'user', 'content': message}], model)
  return response

async def is_asking_for_channel_summary(message):
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message):
  response = await generate_text_from_message(f'Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_image_generation(message):
  response = await generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_multiple_images(message):
  response = await generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}')
  return response.startswith('True')

def is_configured_for_replies_without_tagging(channel):
  if channel['display_name'] == 'Testing':
    return True
  if f"{os.environ['MATTERMOST_BOTNAME']} responds without tagging" in channel['purpose']:
    return True
  return False

def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
