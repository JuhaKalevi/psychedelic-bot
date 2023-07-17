import mattermostdriver.exceptions

async def channel_context(bot, post):
  return await bot.posts.get_posts_for_channel(post['channel_id'])

async def channel_from_post(bot, post):
  return await bot.channels.get_channel(post['channel_id'])

async def create_post(bot, options):
  try:
    return await bot.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')

async def get_mattermost_file(bot, file_id):
  return await bot.files.get_file(file_id=file_id)

async def post_is_from_bot(post):
  return 'from_bot' in post['props']

async def thread_context(bot, post):
  return await bot.posts.get_thread(post['id'])

async def update_post(bot, post_id, options):
  try:
    return await bot.posts.update_post(post_id, options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.update_post(): {err}')

async def upload_mattermost_file(bot, channel_id, files):
  file = await bot.files.upload_file(channel_id, files=files)
  return file['file_infos'][0]['id']
