from os import environ
from asyncio import get_event_loop
from mattermostdriver import Driver
from context_manager import context_manager

async def main():
  mattermost_bot = Driver({'url':environ['MATTERMOST_URL'], 'token':environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
  await mattermost_bot.login()
  await mattermost_bot.init_websocket(context_manager)

get_event_loop().run_until_complete(main())
