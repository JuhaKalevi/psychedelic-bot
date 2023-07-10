import os
import bot
import mattermostdriver

mattermost = mattermostdriver.Driver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
mattermost.login()
mattermost.init_websocket(bot.context_manager)

async def channel_context(post:dict) -> dict:
  bot._return(mattermost.posts.get_posts_for_channel(post['channel_id']))

async def channel_from_post(post:dict) -> dict:
  bot._return(mattermost.channels.get_channel(post['channel_id']))

async def create_post(options:dict) -> None:
  try:
    mattermost.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

async def should_always_reply(channel:dict) -> bool:
  answer = f"{os.environ['MATTERMOST_BOT_NAME']} always reply" in channel['purpose']
  return bot._return(answer)

async def thread_context(post:dict) -> dict:
  context = mattermost.posts.get_thread(post['id'])
  return bot._return(context)

async def upload_file(channel_id:str, files:dict):
  return bot._return(mattermost.files.upload_file(channel_id, files=files)['file_infos'][0]['id'])
