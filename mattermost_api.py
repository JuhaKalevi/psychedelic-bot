import asyncio
import mattermostdriver.exceptions

def channel_context(post, bot):
  context = bot.posts.get_posts_for_channel(post['channel_id'])
  return context

def channel_from_post(post, bot):
  return bot.channels.get_channel(post['channel_id'])

def create_post(options, bot):
  try:
    bot.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

def get_mattermost_file(file_id, bot):
  return bot.files.get_file(file_id=file_id)

def post_is_from_bot(post):
  return 'from_bot' in post['props']

def thread_context(post, bot):
  return bot.posts.get_thread(post['id'])

def upload_mattermost_file(channel_id, files, bot):
  print('upload_mattermost_file')
  return bot.files.upload_file(channel_id, files=files)['file_infos'][0]['id']
