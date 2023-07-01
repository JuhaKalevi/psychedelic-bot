import json
import os
from api_connections import mm, create_mattermost_post, textgen_chat_completion
from language_processing import generate_text_from_context, is_asking_for_image_generation, is_asking_for_multiple_images, is_asking_for_channel_summary
from image_processing import generate_images, upscale_image

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']):
    return
  post = json.loads(event['data']['post'])
  if post['root_id'] == '':
    if os.environ['MATTERMOST_BOTNAME'] not in post['message']:
      if mm.channels.get_channel(post['channel_id'])['type'] != 'D':
        return
      context = mm.posts.get_posts_for_channel(post['channel_id'], params={'page':0, 'per_page':10})
      thread_id = ''
    else:
      context = {'order':[], 'posts':{}}
      thread_id = post['id']
    context['order'].append(post['id'])
    context['posts'][post['id']] = post
    if post['message'].lower().startswith("4x"):
      openai_response_content = upscale_image(file_ids, post)
    elif post['message'].lower().startswith("llm"):
      openai_response_content = textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
    elif is_asking_for_image_generation(post['message']):
      if is_asking_for_multiple_images(post['message']):
        openai_response_content = generate_images(file_ids, post, 8)
      else:
        openai_response_content = generate_images(file_ids, post, 1)
    elif is_asking_for_channel_summary(post['message']) and thread_id == '':
      openai_response_content = generate_text_from_context(mm.channels.get_channel_pinned_posts(post['channel_id']))
    else:
      openai_response_content = generate_text_from_context(context)
  else:
    context = mm.posts.get_thread(post['id'])
    thread_id = post['root_id']
    if not any(os.environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
      return
    openai_response_content = generate_text_from_context(context)
  create_mattermost_post(post['channel_id'], openai_response_content, file_ids, thread_id)

mm.login()
mm.init_websocket(context_manager)
