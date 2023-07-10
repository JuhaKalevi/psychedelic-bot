import json
import os
import sys
import mattermost_api
import img2img
import txt2img
import txt2bool
import txt2txt
import transcription
import webuiapi

webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

async def context_manager(event:dict) -> None:
  file_ids = []
  event = json.loads(event)
  signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOT_NAME']:
    post = json.loads(event['data']['post'])
    signal = await respond_to_magic_words(post, file_ids)
    if signal:
      await mattermost_api.create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':post['root_id']})
    else:
      message = post['message']
      channel = await mattermost_api.channel_from_post(post)
      always_reply = await mattermost_api.should_always_reply(channel)
      if always_reply:
        reply_to = post['root_id']
        signal = await txt2img.consider_image_generation(message, file_ids, post)
        if not signal:
          summarize = await txt2bool.is_asking_for_channel_summary(post)
          if summarize:
            context = await mattermost_api.channel_context(post)
          else:
            context = await mattermost_api.thread_context(post)
          signal = await txt2txt.generate_text_from_context(context)
      elif os.environ['MATTERMOST_BOT_NAME'] in message:
        reply_to = post['root_id']
        context = await txt2txt.generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = await mattermost_api.thread_context(post)
        if any(os.environ['MATTERMOST_BOT_NAME'] in context_post['message'] for context_post in context['posts'].values()):
          signal = await txt2txt.generate_text_from_context(context)
      if signal:
        await mattermost_api.create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':reply_to})

async def respond_to_magic_words(post:dict, file_ids:list):
  lowercase_message = post['message'].lower()
  if lowercase_message.startswith("2x"):
    response = await txt2img.upscale_image_2x(file_ids, post)
  elif lowercase_message.startswith("4x"):
    response = await txt2img.upscale_image_4x(file_ids, post)
  elif lowercase_message.startswith("pix2pix"):
    response = await img2img.instruct_pix2pix(file_ids, post)
  elif lowercase_message.startswith("llm"):
    response = await txt2txt.textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif lowercase_message.startswith("summary"):
    response = await transcription.youtube_transcription(post['message'])
  elif lowercase_message.startswith("caption"):
    response = await transcription.captioner(post)
  elif lowercase_message.startswith("storyteller"):
    response = await transcription.storyteller(post)
  else:
    return None
  return _return(response)

async def _return(data):
  if os.environ['LOG_LEVEL'] == 'TRACE':
    print(f"TRACE {sys._getframe(1).f_code.co_name}: len(data)={len(data)}")
  return data
