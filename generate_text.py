import json
import os
import tiktoken
import log
import openai_api

logger = log.get_logger(__name__)

async def choose_system_message(post):
  system_message = []
  if await is_asking_for_code_analysis(post['message']):
    files = []
    for file_path in [x for x in os.listdir() if x.endswith(('.py','.sh','.yml'))]:
      with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
      files.append(f'--- BEGIN {file_path} ---\n{content}\n--- END {file_path} ---\n')
    system_message.append({'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(files)})
  return system_message

def count_tokens(message):
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def fix_image_generation_prompt(message):
  return await from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}")

async def from_context_streamed(context, model='gpt-4'):
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]])
  context_messages = []
  context_tokens = count_tokens(system_message)
  context_token_limit = 7372
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role':role, 'content':context['posts'][post_id]['message']}
    message_tokens = count_tokens(message)
    new_context_tokens = context_tokens + message_tokens
    if context_token_limit < new_context_tokens < 14744:
      model = 'gpt-3.5-turbo-16k'
      context_token_limit *= 2
    elif new_context_tokens > 14744:
      break
    context_messages.append(message)
    context_tokens = new_context_tokens
  context_messages.reverse()
  logger.debug('token_count: %s', context_tokens)
  async for content in openai_api.chat_completion_streamed(system_message + context_messages, model):
    yield content

async def from_message(message, model='gpt-4'):
  return await openai_api.chat_completion([{'role':'user', 'content':message}], model)

async def from_message_streamed(message, model='gpt-4'):
  async for content in openai_api.chat_completion_streamed([{'role':'user', 'content':message}], model):
    yield content

async def is_asking_for_channel_summary(message):
  response = await from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message):
  response = await from_message(f"Is this a message where knowledge or analysis of your code files is requested? You have a function that we will use later on if needed to read these files. Answer only True or False: {message}")
  return response.startswith('True')
