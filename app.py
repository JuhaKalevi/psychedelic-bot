import asyncio
import json
import os
from api_mattermost import mm, create_mattermost_post
from api_oobabooga_textgen import textgen_chat_completion
from api_stable_diffusion_webui import generate_images, upscale_image
from language_processing import generate_text_from_context, is_asking_for_image_generation, is_asking_for_multiple_images, is_asking_for_channel_summary

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if not ('event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']):
    return
  new_post = json.loads(event['data']['post'])
  if new_post['root_id'] == '':
    if os.environ['MATTERMOST_BOTNAME'] in new_post['message']:
      thread_id = new_post['id']
      context = {'order':[new_post['id']], 'posts':{new_post['id']:new_post}}
    elif mm.channels.get_channel(new_post['channel_id'])['type'] != 'D' and mm.channels.get_channel(new_post['channel_id'])['display_name'] != 'Testing':
      return
    else:
      thread_id = ''
      context = mm.posts.get_posts_for_channel(new_post['channel_id'])
    if new_post['message'].lower().startswith("4x"):
      openai_response_content = await upscale_image(file_ids, new_post)
    elif new_post['message'].lower().startswith("llm"):
      openai_response_content = await textgen_chat_completion(new_post['message'], {'internal': [], 'visible': []})
    elif await is_asking_for_image_generation(new_post['message']):
      if await is_asking_for_multiple_images(new_post['message']):
        openai_response_content = await generate_images(file_ids, new_post, 8)
      else:
        openai_response_content = await generate_images(file_ids, new_post, 1)
    elif await is_asking_for_channel_summary(new_post['message']) and thread_id != '':
      openai_response_content = await generate_text_from_context(mm.channels.get_channel_pinned_posts(new_post['channel_id']))
    else:
      openai_response_content = await generate_text_from_context(context)
  else:
    thread_id = new_post['root_id']
    context = mm.posts.get_thread(thread_id)
    if not any(os.environ['MATTERMOST_BOTNAME'] in context_post['message'] for context_post in context['posts'].values()):
      return
    openai_response_content = generate_text_from_context(context)
  mm_response = await create_mattermost_post(new_post['channel_id'], openai_response_content, file_ids, thread_id)
  print(mm_response)

async def run_chatbot():
  login_status = await mm.login()
  print(login_status)
  await mm.init_websocket(context_manager)

asyncio.run(run_chatbot())
