import os
import json
import chardet
import langdetect
import tiktoken
import mattermost_api
import openai_api

bot_name = os.environ['MATTERMOST_BOT_NAME']

def bot_name_in_message(message):
  return bot_name in message or bot_name == '@chatbot' and '@chatgpt' in message

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

async def generate_story_from_captions(message, model='gpt-4'):
  story = await openai_api.openai_chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)
  return story

async def generate_summary_from_transcription(message, model='gpt-4'):
  response = await openai_api.openai_chat_completion([
    {
      'role': 'user',
      'content': (f"Summarize in appropriate detail, adjusting the summary length"
        f" according to the transcription's length, the YouTube-video transcription below."
        f" Also make a guess on how many different characters' speech is included in the transcription."
        f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
        f" IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s),"
        f" all War Thunder/Athletic Green etc. talk completely. Also give scoring 0-10 about the video for each of these three categories: originality, difficulty, humor, boringness, creativity, artful, . Transcription: {message}")
    }
], model)
  return response

async def count_tokens(message):
  token_count = len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))
  return token_count

async def fix_image_generation_prompt(message):
  fixed_prompt = await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}")
  return fixed_prompt

async def generate_text_from_context(context, model='gpt-4'):
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await choose_system_message(context['posts'][context['order'][0]])
  context_messages = []
  context_tokens = await count_tokens(system_message)
  for post_id in context['order']:
    if mattermost_api.post_is_from_bot(context['posts'][post_id]):
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
  openai_response = await openai_api.openai_chat_completion(system_message + context_messages, model)
  return openai_response

async def generate_text_from_message(message, model='gpt-4'):
  response = await openai_api.openai_chat_completion([{'role':'user', 'content':message}], model)
  return response

async def is_asking_for_channel_summary(message):
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message):
  response = await generate_text_from_message(f"Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}")
  return response.startswith('True')

async def is_asking_for_image_generation(message):
  response = await generate_text_from_message(f"Is this a message where an image is probably requested? Answer only True or False: {message}")
  return response.startswith('True')

async def is_asking_for_multiple_images(message):
  response = await generate_text_from_message(f"Is this a message where multiple images are requested? Answer only True or False: {message}")
  return response.startswith('True')

def is_mainly_english(text):
  response = langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
  return response

def should_always_reply(channel_purpose):
  should_reply = f"{bot_name} always reply" in channel_purpose
  return should_reply
