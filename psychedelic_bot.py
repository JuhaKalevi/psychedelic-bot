import asyncio
import json
import mattermost_api
import mattermost_post_handler

bot = mattermost_api.bot

async def context_manager(_event:str):
  event = json.loads(_event)
  if event.get('event') == 'posted' and event['data']['sender_name'] != bot.name:
    post = json.loads(event['data']['post'])
    if 'from_bot' not in post['props']:
      asyncio.create_task(mattermost_post_handler.MattermostPostHandler(post).post_handler())

async def main():
  await bot.login()
  await bot.init_websocket(context_manager)

asyncio.run(main())
