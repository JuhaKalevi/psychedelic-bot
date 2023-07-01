import json
import os
import chardet
import langdetect
import tiktoken
from api_connections import openai_chat_completion

def count_tokens(message):
  encoding = tiktoken.get_encoding('cl100k_base')
  return len(encoding.encode(json.dumps(message)))

def generate_text_from_context(context):
  tokens = 0
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role': role, 'content': context['posts'][post_id]['message']}
    message_tokens = count_tokens(message)
    if tokens + message_tokens < 7777:
      messages.append(message)
      tokens += message_tokens
    else:
      break
  if tokens < 4000:
    messages = select_system_message(context['posts'][post_id]['message']) + messages
  return openai_chat_completion(messages, os.environ['OPENAI_MODEL_NAME'])

def generate_text_from_message(message, model='gpt-4'):
  return openai_chat_completion([{'role': 'user', 'content': message}], model)

def is_asking_for_image_generation(message):
  return generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}').startswith('True')

def is_asking_for_multiple_images(message):
  return generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}').startswith('True')

def is_asking_for_channel_summary(message):
  return generate_text_from_message(f'Is this a message where a summary of past conversations in this channel is requested? Answer only True or False: {message}').startswith('True')

def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"

def select_system_message(message):
  system_message = []
  code_snippets = []
  if message.startswith('@code-analysis') or generate_text_from_message(f"Is this a message where knowledge or analysis of your code is requested? It doesn't matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False!: {message}").startswith('True'):
    for file_path in ['api_connections.py', 'app.py', 'image_processing.py', 'language_processing.py']:
      with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
      code_snippets.append(f"--- {file_path} ---\n{code}\n")
    system_message.append({'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)})
  return system_message
