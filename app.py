import json
import os
import mattermostdriver
from api_connections import mm, textgen_chat_completion
from language_processing import generate_text_from_context, is_asking_for_image_generation, is_asking_for_multiple_images
from image_processing import generate_images, upscale_image

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']:
    post = json.loads(event['data']['post'])
    if post['root_id'] == "":
      if os.environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      if post['message'].lower().startswith("4x"):
        openai_response_content = upscale_image(file_ids, post)
      elif post['message'].lower().startswith("LLM"):
        openai_response_content = textgen_chat_completion(post['message'])
      elif is_asking_for_image_generation(post['message']):
        if is_asking_for_multiple_images(post['message']):
          openai_response_content = generate_images(file_ids, post, 8)
        else:
          openai_response_content = generate_images(file_ids, post, 1)
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text_from_context(context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(os.environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text_from_context(context)
    try:
      mm.posts.create_post(options={'channel_id':post['channel_id'], 'message':openai_response_content, 'file_ids':file_ids, 'root_id':thread_id})
    except (mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f"Mattermost API Error: {err}")

mm.login()
mm.init_websocket(context_manager)
