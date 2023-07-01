import os
import mattermostdriver
from app import context_manager

mm = mattermostdriver.Driver({
  'url': os.environ['MATTERMOST_URL'],
  'token': os.environ['MATTERMOST_TOKEN'],
  'scheme':'https',
  'port':443
})
mm.login()
mm.init_websocket(context_manager)

def create_mattermost_post(channel_id, message, file_ids, thread_id):
  try:
    mm.posts.create_post(options={'channel_id':channel_id, 'message':message, 'file_ids':file_ids, 'root_id':thread_id})
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    print(f"Mattermost API Error: {err}")
