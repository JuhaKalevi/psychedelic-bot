from os import environ
from mattermostdriver import Driver
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound

mm = Driver({'url': environ['MATTERMOST_URL'], 'token': environ['MATTERMOST_TOKEN'], 'port': 443})

def create_mattermost_post(channel_id, message, file_ids, thread_id):
  try:
    mm.posts.create_post(options={'channel_id':channel_id, 'message':message, 'file_ids':file_ids, 'root_id':thread_id})
  except (InvalidOrMissingParameters, ResourceNotFound) as err:
    print(f"Mattermost API Error: {err}")
