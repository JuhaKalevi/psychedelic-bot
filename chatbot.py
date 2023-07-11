from asyncio import get_event_loop
from context_manager import context_manager
from mattermost_bot import mattermost_bot

async def main():
  mattermost_bot.login()
  mattermost_bot.init_websocket(context_manager)

if __name__ == "__main__":
  get_event_loop().run_until_complete(main())
