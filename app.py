import json
import os
from api_mattermost import mm, create_mattermost_post
from api_oobabooga_textgen import textgen_chat_completion
from api_stable_diffusion_webui import generate_images, upscale_image_2x, upscale_image_4x, instruct_pix2pix
from language_processing import generate_text_from_context, is_asking_for_image_generation, is_asking_for_multiple_images, is_asking_for_channel_summary, is_configured_for_replies_without_tagging

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']):
    return
  post = json.loads(event['data']['post'])
  if is_configured_for_replies_without_tagging(mm.channels.get_channel(post['channel_id'])):
      thread_id = ''
      context = mm.posts.get_posts_for_channel(post['channel_id'])
  elif post['root_id'] == '':
    if os.environ['MATTERMOST_BOTNAME'] in post['message']:
      thread_id = post['id']
      if await is_asking_for_channel_summary(post['message']):
        context = mm.posts.get_posts_for_channel(post['channel_id'])
      else:
        context = {'order':[post['id']], 'posts':{post['id']:post}}
    if post['message'].lower().startswith("2x"):
      openai_response_content = await upscale_image_2x(file_ids, post)
    elif post['message'].lower().startswith("4x"):
      openai_response_content = await upscale_image_4x(file_ids, post)
    elif post['message'].lower().startswith("pix2pix"):
      openai_response_content = await instruct_pix2pix(file_ids, post)
    elif post['message'].lower().startswith("llm"):
      openai_response_content = await textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
    elif await is_asking_for_image_generation(post['message']):
      if await is_asking_for_multiple_images(post['message']):
        openai_response_content = await generate_images(file_ids, post, 8)
      else:
        openai_response_content = await generate_images(file_ids, post, 1)
    else:
      openai_response_content = await generate_text_from_context(context)
  else:
    thread_id = post['root_id']
    context = mm.posts.get_thread(thread_id)
    if not any(os.environ['MATTERMOST_BOTNAME'] in context_post['message'] for context_post in context['posts'].values()):
      return
    openai_response_content = await generate_text_from_context(context)
  create_mattermost_post(post['channel_id'], openai_response_content, file_ids, thread_id)

mm.login()
mm.init_websocket(context_manager)
