import os
import mattermostdriver
import context_manager

bot = mattermostdriver.Driver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot.login()

bot.init_websocket(context_manager.context_manager)
