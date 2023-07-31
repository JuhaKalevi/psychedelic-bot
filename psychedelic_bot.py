import asyncio
import json
import log
import multimedia
import mattermost_api
import mattermost_post_handler

bot = mattermost_api.bot
logger = log.get_logger(__name__)
tasks = []

available_functions = {
  'generate_images': multimedia.generate_images
}

async def context_manager(event):
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != bot.name:
    post = json.loads(event['data']['post'])
    if 'from_bot' not in post['props']:
      asyncio.create_task(mattermost_post_handler.MattermostPostHandler(post, available_functions).post_handler())

async def main():
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
