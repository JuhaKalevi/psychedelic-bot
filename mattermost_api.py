import os
import mattermostdriver.exceptions
class MattermostBot(mattermostdriver.AsyncDriver):

  name = os.environ['MATTERMOST_BOT_NAME']
  
  async def create_or_update_post(self, options:dict, post_id=None):
    try:
      if post_id:
        post = await self.posts.patch_post(post_id, options=options)
      else:
        post = await self.posts.create_post(options=options)
      return post['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f'ERROR mattermost.posts.create_post(): {err}')

  def name_in_message(self, message:str) -> bool:
    return self.name in message or self.name == '@bot' and '@chatgpt' in message

  async def tag_post_with_emoji(self, post_id:str, emoji:str):
    try:
      user_id = await self.users.get_user_by_username(self.name)
      return await self.reactions.create_reaction({'user_id': user_id, 'post_id':post_id, 'emoji_name':emoji})
    except mattermostdriver.exceptions.ResourceNotFound as err:
      print(f'ERROR mattermost.reactions.create_reaction(): {err}')

  async def upload_mattermost_file(self, channel_id:str, files):
    try:
      file = await self.files.upload_file(channel_id, files=files)
      return file['file_infos'][0]['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f'ERROR mattermost.files.upload_file(): {err}')

bot = MattermostBot({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'], 'scheme':'https', 'port':443})
