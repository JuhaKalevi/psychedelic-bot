from context_manager import context_manager
from mattermost_bot import mattermost_bot

mattermost_bot.login()
mattermost_bot.init_websocket(context_manager)
