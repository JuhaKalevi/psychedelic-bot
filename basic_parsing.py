import os
import json
import chardet
import langdetect
import tiktoken
from openai_api import openai_chat_completion

bot_name = os.environ['MATTERMOST_BOT_NAME']
CODE_ANALYSIS_CHANNELS = [
  'GitLab',
  'Testing'
]

async def choose_system_message(post, channel):
  if channel['display_name'] in CODE_ANALYSIS_CHANNELS or await is_asking_for_code_analysis(post['message'], channel):
    code_snippets = []
    for file_path in [x for x in os.listdir() if x.endswith('.py')]:
      with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
      code_snippets.append(f'--- BEGIN {file_path} ---\n{code}\n')
    default_system_message = [{'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)}]
  else:
    default_system_message = [{'role':'system', 'content':'You are an assistant with no specific role determined right now.'}]
  return default_system_message

async def generate_story_from_captions(message, model='gpt-4'):
  story = await openai_chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)
  return story

async def count_tokens(message):
  print ('count_tokens')
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def fix_image_generation_prompt(message):
  fixed_prompt = await generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {message}")
  return fixed_prompt

async def generate_text_from_message(message, model='gpt-4'):
  response = await openai_chat_completion([{'role':'user', 'content':message}], model)
  return response

async def is_asking_for_channel_summary(message, channel):
  print('is_asking_for_channel_summary')
  if channel['purpose'] == f"{bot_name} use channel context":
    return True
  response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_code_analysis(message, channel):
  if channel['purpose'] == f"{bot_name} analyze your code":
    return True
  response = await generate_text_from_message(f"Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}")
  return response.startswith('True')

async def is_asking_for_image_generation(message):
  print('is_asking_for_image_generation')
  response = await generate_text_from_message(f"Is this a message where an image is probably requested? Answer only True or False: {message}")
  return response.startswith('True')

async def is_asking_for_multiple_images(message):
  response = await generate_text_from_message(f"Is this a message where multiple images are requested? Answer only True or False: {message}")
  return response.startswith('True')

def is_mainly_english(text):
  response = langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
  return response

def should_always_reply_on_channel(channel_purpose):
  print('should_always_reply_on_channel')
  return f"{bot_name} always reply" in channel_purpose
