import os
import mattermostdriver.exceptions
class MattermostBot(mattermostdriver.AsyncDriver):

  name = os.environ['MATTERMOST_BOT_NAME']

  async def create_or_update_post(self, options:dict, post_id=None) -> str:
    try:
      if post_id:
        post = await self.posts.patch_post(post_id, options=options)
      else:
        post = await self.posts.create_post(options=options)
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f'ERROR mattermost.posts.create_post(): {err}')
    return post['id']

  def name_in_message(self, message:str) -> bool:
    return self.name in message or self.name == '@bot' and '@chatgpt' in message

  async def upload_mattermost_file(self, channel_id:str, files):
    try:
      file = await self.files.upload_file(channel_id, files=files)
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f'ERROR mattermost.files.upload_file(): {err}')
    return file['file_infos'][0]['id']

bot = MattermostBot({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
