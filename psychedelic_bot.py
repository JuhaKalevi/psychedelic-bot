import asyncio
from json import loads
from os import environ
import mattermostdriver.exceptions
import actions

class PsychedelicBot(mattermostdriver.AsyncDriver):

  def __init__(self):
    self.name = environ['MATTERMOST_BOT_NAME']
    self.user_id = ''
    super().__init__({'url':environ['MATTERMOST_URL'], 'token':environ['MATTERMOST_TOKEN'], 'scheme':'https', 'port':443})
    asyncio.create_task(self.__listener__())

  async def __listener__(self):
    await self.login()
    await self.init_websocket(self.context_manager)

  async def context_manager(self, raw_event:str):
    event = loads(raw_event)
    if event.get('event') == 'posted' and event['data']['sender_name'] != self.name:
      post = loads(event['data']['post'])
      if 'from_bot' not in post['props']:
        actions.Mattermost(self, post)

  async def create_or_update_post(self, opts:dict, _id=None):
    try:
      if _id:
        post = await self.posts.patch_post(_id, options=opts)
      else:
        post = await self.posts.create_post(options=opts)
      return post['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      return err

  async def create_reaction(self, post_id:str, emoji:str):
    try:
      reaction = await self.reactions.create_reaction(options={'user_id':self.user_id, 'post_id':post_id, 'emoji_name':emoji})
      return reaction
    except mattermostdriver.exceptions.ResourceNotFound as err:
      return err

  def name_in_message(self, message:str):
    return self.name in message or self.name == '@bot' and '@chatgpt' in message

  async def upload_file(self, channel_id:str, files):
    try:
      file = await self.files.upload_file(channel_id, files=files)
      return file['file_infos'][0]['id']
    except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      return err

asyncio.run(PsychedelicBot())
