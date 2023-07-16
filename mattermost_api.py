import mattermostdriver.exceptions

async def channel_context(bot, post):
  context = await bot.posts.get_posts_for_channel(post['channel_id'])
  return context

async def channel_from_post(bot, post):
  return await bot.channels.get_channel(post['channel_id'])

async def create_post(bot, options):
  try:
    await bot.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

async def get_mattermost_file(bot, file_id):
  file = await bot.files.get_file(file_id=file_id)
  return file

def post_is_from_bot(post):
  return 'from_bot' in post['props']

async def thread_context(bot, post):
  context = await bot.posts.get_thread(post['id'])
  return context

def upload_mattermost_file(bot, channel_id, files):
  print('upload_mattermost_file')
  return bot.files.upload_file(channel_id, files=files)['file_infos'][0]['id']
