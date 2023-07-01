import json
import os
import tiktoken
from api_connections import mm, create_mattermost_post, textgen_chat_completion
from language_processing import generate_text_from_context, is_asking_for_image_generation, is_asking_for_multiple_images, is_asking_for_channel_summary
from image_processing import generate_images, upscale_image

def num_tokens_from_string(string, model='gpt-4'):
  return len(tiktoken.get_encoding(tiktoken.encoding_for_model(model)).encode(string))

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']):
    return
  post = json.loads(event['data']['post'])
  if post['root_id'] == '':
    if os.environ['MATTERMOST_BOTNAME'] in post['message']:
      thread_id = post['id']
      context = {'order':[post['id']], 'posts':{post['id']:post}}
    elif mm.channels.get_channel(post['channel_id'])['type'] != 'D' and mm.channels.get_channel(post['channel_id'])['display_name'] != 'Testing':
      return
    else:
      thread_id = ''
      context = {'order':[], 'posts':{}}
      tokens = 0
      page = 0
      per_page = 10
      while tokens < 7777:
        for channel_post in mm.posts.get_posts_for_channel(post['channel_id'], params={'page':page, 'per_page':per_page}):
          if channel_post['root_id'] == '':
            context['order'].append(channel_post['id'])
            context['posts'][channel_post['id']] = channel_post
            tokens += num_tokens_from_string(channel_post['message'])
        page += per_page
    if post['message'].lower().startswith("4x"):
      openai_response_content = upscale_image(file_ids, post)
    elif post['message'].lower().startswith("llm"):
      openai_response_content = textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
    elif is_asking_for_image_generation(post['message']):
      if is_asking_for_multiple_images(post['message']):
        openai_response_content = generate_images(file_ids, post, 8)
      else:
        openai_response_content = generate_images(file_ids, post, 1)
    elif is_asking_for_channel_summary(post['message']) and thread_id != '':
      openai_response_content = generate_text_from_context(mm.channels.get_channel_pinned_posts(post['channel_id']))
    else:
      openai_response_content = generate_text_from_context(context)
  else:
    thread_id = post['root_id']
    context = mm.posts.get_thread(post['id'])
    if not any(os.environ['MATTERMOST_BOTNAME'] in context_post['message'] for context_post in context['posts'].values()):
      return
    openai_response_content = generate_text_from_context(context)
  create_mattermost_post(post['channel_id'], openai_response_content, file_ids, thread_id)

mm.login()
mm.init_websocket(context_manager)
