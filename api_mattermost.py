import os
import mattermostdriver

mm = mattermostdriver.Driver({
  'url': os.environ['MATTERMOST_URL'],
  'token': os.environ['MATTERMOST_TOKEN'],
  'scheme':'https',
  'port':443
})

async def create_mattermost_post(channel_id, message, file_ids, thread_id):
  try:
    response = await mm.posts.create_post(options={'channel_id':channel_id, 'message':message, 'file_ids':file_ids, 'root_id':thread_id})
    return response
  except (ConnectionResetError, mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
    return f"Mattermost API Error: {err}"
