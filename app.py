from mattermost_bot import mattermost_bot, context_manager

mattermost_bot.login()
mattermost_bot.init_websocket(context_manager)
