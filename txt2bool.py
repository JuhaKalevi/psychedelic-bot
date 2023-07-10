import chardet
import langdetect
from bot import channel_from_post
from txt2txt import generate_text_from_message

async def is_asking_for_channel_summary(post:dict) -> bool:
  channel = await channel_from_post(post)
  if channel['display_name'] == 'GitLab':
    response = 'True'
  else:
    response = await generate_text_from_message(f'Is this a message where a summary of past interactions in this chat/discussion/channel is requested? Answer only True or False: {post["message"]}')
  return response.startswith('True')

async def is_asking_for_code_analysis(post:dict) -> bool:
  message = post['message']
  channel = await channel_from_post(post)
  if channel['display_name'] == 'GitLab':
    response = 'True'
  elif message.startswith('@code-analysis'):
    response = 'True'
  else:
    response = await generate_text_from_message(f'Is this a message where knowledge or analysis of your code is requested? It does not matter whether you know about the files or not yet, you have a function that we will use later on if needed. Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_image_generation(message:dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_asking_for_multiple_images(message:dict) -> bool:
  response = await generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}')
  return response.startswith('True')

async def is_mainly_english(text:str) -> bool:
  response = langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
  return response
