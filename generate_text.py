import json
import os
import tiktoken
import openai_api

async def choose_system_message(post):
  if await is_asking_for_code_analysis(post['message']):
    code_snippets = []
    for file_path in [x for x in os.listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGIN {file_path} ---\n{code}\n')
    default_system_message = [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  else:
    default_system_message = []
  return default_system_message

async def count_tokens(message):
  token_count = len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))
  return token_count

async def fix_image_generation_prompt(message):
  async for response in from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}"):
    return response

async def from_context(context, model='gpt-4'):
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]])
  context_messages = []
  context_tokens = await count_tokens(system_message)
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role':role, 'content':context['posts'][post_id]['message']}
    message_tokens = await count_tokens(message)
    if context_tokens + message_tokens < 7777:
      context_messages.append(message)
      context_tokens += message_tokens
    else:
      break
  context_messages.reverse()
  async for content in openai_api.openai_chat_completion(system_message + context_messages, model):
    yield content

async def from_message(message, model='gpt-4'):
  async for content in openai_api.openai_chat_completion([{'role':'user', 'content':message}], model):
    yield content

async def is_asking_for_channel_summary(message):
  async for response in from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}'):
    return response.startswith('True')

async def is_asking_for_code_analysis(message):
  async for response in from_message(f"Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}"):
    return response.startswith('True')

async def is_asking_for_image_generation(message):
  async for response in from_message(f"Is this a message where an image is probably requested? Answer only True or False: {message}"):
    return response.startswith('True')

async def is_asking_for_multiple_images(message):
  async for response in from_message(f"Is this a message where multiple images are requested? Answer only True or False: {message}"):
    return response.startswith('True')
