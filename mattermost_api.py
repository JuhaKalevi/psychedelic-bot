import mattermostdriver.exceptions

async def create_or_update_post(bot, options, post_id=None):
  try:
    if post_id:
      post = await bot.posts.patch_post(post_id, options=options)
    else:
      post = await bot.posts.create_post(options=options)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.posts.create_post(): {err}')
  return post['id']

async def upload_mattermost_file(bot, channel_id, files):
  try:
    file = await bot.files.upload_file(channel_id, files=files)
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f'ERROR mattermost.files.upload_file(): {err}')
  return file['file_infos'][0]['id']
