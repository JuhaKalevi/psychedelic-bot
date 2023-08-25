import os
import mattermostdriver.exceptions

class MattermostBot(mattermostdriver.AsyncDriver):

  name = os.environ['MATTERMOST_BOT_NAME']
  user_id = ''

  async def create_or_update_post(self, options:dict, post_id=None):
    try:
      if post_id:
        post = await self.posts.patch_post(post_id, options=options)
      else:
        post = await self.posts.create_post(options=options)
      return post['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      return err

  async def react(self, post_id:str, emoji:str):
    try:
      reaction = await self.reactions.create_reaction(options={'user_id':self.user_id, 'post_id':post_id, 'emoji_name':emoji})
      return reaction
    except mattermostdriver.exceptions.ResourceNotFound as err:
      return err

  def name_in_message(self, message:str) -> bool:
    return self.name in message or self.name == '@bot' and '@chatgpt' in message

  async def upload_file(self, channel_id:str, files):
    try:
      file = await self.files.upload_file(channel_id, files=files)
      return file['file_infos'][0]['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      return err

bot = MattermostBot({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'], 'scheme':'https', 'port':443})
