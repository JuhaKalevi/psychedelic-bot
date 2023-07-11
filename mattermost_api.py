from mattermostdriver import Driver

def channel_context(post:dict, bot) -> dict:
  return bot.posts.get_posts_for_channel(post['channel_id'])

def channel_from_post(post:dict, bot) -> dict:
  return bot.channels.get_channel(post['channel_id'])

def create_post(options:dict, bot) -> None:
  from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound
  try:
    bot.posts.create_post(options=options)
  except (ConnectionResetError, InvalidOrMissingParameters, ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

def get_mattermost_file(file_id:str, bot:Driver) -> dict:
  return bot.files.get_file(file_id=file_id)

def thread_context(post:dict, bot:Driver) -> dict:
  return bot.posts.get_thread(post['id'])

def upload_mattermost_file(channel_id:str, files:dict, bot:str):
  return bot.files.upload_file(channel_id, files=files)['file_infos'][0]['id']
