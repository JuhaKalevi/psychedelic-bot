import json
import tiktoken
import log
import openai_api

logger = log.get_logger(__name__)

def count_tokens(message):
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def fix_image_generation_prompt(message):
  return await from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}")

async def from_context_streamed(context, model='gpt-4'):
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  context_messages = []
  context_tokens = 0
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
  async for content in openai_api.chat_completion_streamed(context_messages, model):
    yield content

async def from_message(message, model='gpt-4'):
  return await openai_api.chat_completion([{'role':'user', 'content':message}], model)

async def from_message_streamed(message, model='gpt-4'):
  async for content in openai_api.chat_completion_streamed([{'role':'user', 'content':message}], model):
    yield content
