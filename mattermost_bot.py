from os import environ
from mattermostdriver import Driver
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound

mattermost_bot = Driver({'url':environ['MATTERMOST_URL'], 'token':environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})

async def channel_context(post:dict) -> dict:
  return mattermost_bot.posts.get_posts_for_channel(post['channel_id'])

async def channel_from_post(post:dict) -> dict:
  return mattermost_bot.channels.get_channel(post['channel_id'])

async def create_post(options:dict) -> None:
  try:
    mattermost_bot.posts.create_post(options=options)
  except (ConnectionResetError, InvalidOrMissingParameters, ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

async def get_mattermost_file(file_id:str) -> dict:
  return mattermost_bot.files.get_file(file_id=file_id)

async def thread_context(post:dict) -> dict:
  return mattermost_bot.posts.get_thread(post['id'])

async def should_always_reply(channel:dict) -> bool:
  return f"{environ['MATTERMOST_BOT_NAME']} always reply" in channel['purpose']

async def upload_mattermost_file(channel_id:str, files:dict):
  return mattermost_bot.files.upload_file(channel_id, files=files)['file_infos'][0]['id']
