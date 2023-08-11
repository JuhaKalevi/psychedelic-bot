import asyncio
import json
import log
import mattermost_api
import mattermost_post_handler

bot = mattermost_api.bot
logger = log.get_logger(__name__)

async def context_manager(_event:str) -> None:
  event = json.loads(_event)
  if event.get('event') == 'posted' and event['data']['sender_name'] != bot.name:
    post = json.loads(event['data']['post'])
    logger.debug(post)
    if 'from_bot' not in post['props']:
      asyncio.create_task(mattermost_post_handler.MattermostPostHandler(post).post_handler())

async def main() -> None:
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
