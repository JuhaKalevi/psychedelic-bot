from json import loads
from os import environ
from mattermostdriver import Driver
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound
from img2txt import captioner, storyteller
from img2img import instruct_pix2pix, upscale_image_2x, upscale_image_4x
from txt2bool import is_asking_for_channel_summary
from txt2img import consider_image_generation
from txt2txt import generate_text_from_context, generate_text_from_message, textgen_chat_completion
from vid2txt import youtube_transcription

mattermost_bot = Driver({'url':environ['MATTERMOST_URL'], 'token':environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})

async def channel_context(post:dict) -> dict:
  return mattermost_bot.posts.get_posts_for_channel(post['channel_id'])

async def channel_from_post(post:dict) -> dict:
  return mattermost_bot.channels.get_channel(post['channel_id'])

async def context_manager(event:dict) -> None:
  file_ids = []
  event = loads(event)
  signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != environ['MATTERMOST_BOT_NAME']:
    post = loads(event['data']['post'])
    signal = await respond_to_magic_words(post, file_ids)
    if signal:
      await create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':post['root_id']})
    else:
      message = post['message']
      channel = await channel_from_post(post)
      always_reply = await should_always_reply(channel)
      if always_reply:
        reply_to = post['root_id']
        signal = await consider_image_generation(message, file_ids, post)
        if not signal:
          summarize = await is_asking_for_channel_summary(post)
          if summarize:
            context = await channel_context(post)
          else:
            context = await thread_context(post)
          signal = await generate_text_from_context(context)
      elif environ['MATTERMOST_BOT_NAME'] in message:
        reply_to = post['root_id']
        context = await generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = await thread_context(post)
        if any(environ['MATTERMOST_BOT_NAME'] in context_post['message'] for context_post in context['posts'].values()):
          signal = await generate_text_from_context(context)
      if signal:
        await create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':reply_to})

async def create_post(options:dict) -> None:
  try:
    mattermost_bot.posts.create_post(options=options)
  except (ConnectionResetError, InvalidOrMissingParameters, ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

async def get_mattermost_file(file_id:str) -> dict:
  return mattermost_bot.files.get_file(file_id=file_id)

async def thread_context(post:dict) -> dict:
  return mattermost_bot.posts.get_thread(post['id'])

async def respond_to_magic_words(post:dict, file_ids:list):
  lowercase_message = post['message'].lower()
  if lowercase_message.startswith("caption"):
    magic_response = await captioner(file_ids)
  elif lowercase_message.startswith("pix2pix"):
    magic_response = await instruct_pix2pix(file_ids, post)
  elif lowercase_message.startswith("2x"):
    magic_response = await upscale_image_2x(file_ids, post)
  elif lowercase_message.startswith("4x"):
    magic_response = await upscale_image_4x(file_ids, post)
  elif lowercase_message.startswith("llm"):
    magic_response = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif lowercase_message.startswith("storyteller"):
    magic_response = await storyteller(post)
  elif lowercase_message.startswith("summary"):
    magic_response = await youtube_transcription(post['message'])
  else:
    return None
  return magic_response

async def should_always_reply(channel:dict) -> bool:
  return f"{environ['MATTERMOST_BOT_NAME']} always reply" in channel['purpose']

async def upload_mattermost_file(channel_id:str, files:dict):
  return mattermost_bot.files.upload_file(channel_id, files=files)['file_infos'][0]['id']
