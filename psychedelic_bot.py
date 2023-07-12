import json
import os
import mattermostdriver
import basic
import multimedia
import mattermost_api
import openai_api
import textgen_api

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  return_signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != basic.bot_name:
    post = json.loads(event['data']['post'])
    return_signal = await respond_to_magic_words(post, file_ids)
    if return_signal:
      mattermost_api.create_post({'channel_id':post['channel_id'], 'message':return_signal, 'file_ids':file_ids, 'root_id':post['root_id']}, bot)
    else:
      message = post['message']
      channel = mattermost_api.channel_from_post(post, bot)
      always_reply = basic.should_always_reply_on_channel(channel['purpose'])
      if always_reply or basic.bot_name in message:
        reply_to = post['root_id']
        return_signal = await consider_image_generation(message, file_ids, post)
        if not return_signal:
          summarize = await basic.is_asking_for_channel_summary(message, channel)
          if summarize:
            print('summarize')
            context = mattermost_api.channel_context(post, bot)
          else:
            context = mattermost_api.thread_context(post, bot)
          return_signal = await generate_text_from_context(context, channel)
      elif basic.bot_name in message:
        print(f"{channel['display_name']}: bot_name in message")
        reply_to = post['root_id']
        context = await basic.generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = mattermost_api.thread_context(post, bot)
        if any(basic.bot_name in context_post['message'] for context_post in context['posts'].values()):
          return_signal = await generate_text_from_context(context, channel)
      if return_signal:
        print(f"{channel['display_name']}: create_post: {return_signal}")
        mattermost_api.create_post({'channel_id':post['channel_id'], 'message':return_signal, 'file_ids':file_ids, 'root_id':reply_to}, bot)

async def consider_image_generation(message, file_ids, post):
  image_requested = await basic.is_asking_for_image_generation(message)
  print(f"consider_image_generation")
  if image_requested:
    asking_for_multiple_images = await basic.is_asking_for_multiple_images(message)
    if asking_for_multiple_images:
      image_generation_comment = await multimedia.generate_images(bot, file_ids, post, 8)
    else:
      image_generation_comment = await multimedia.generate_images(bot, file_ids, post, 1)
    return image_generation_comment
  return ''

async def generate_text_from_context(context, channel, model='gpt-4'):
  print(f"{channel['display_name']}: generate_text_from_context")
  if 'order' in context:
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'], reverse=True)
  system_message = await basic.choose_system_message(context['posts'][context['order'][0]], channel)
  context_messages = []
  context_tokens = await basic.count_tokens(context)
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    message = {'role': role, 'content': context['posts'][post_id]['message']}
    message_tokens = await basic.count_tokens(message)
    if context_tokens + message_tokens < 7777:
      context_messages.append(message)
      context_tokens += message_tokens
    else:
      break
  context_messages.reverse()
  openai_response = await openai_api.openai_chat_completion(system_message + context_messages, model)
  return openai_response

async def respond_to_magic_words(post, file_ids):
  word = post['message'].lower()
  if word.startswith("caption"):
    print('caption')
    response = await multimedia.captioner(bot, file_ids)
  elif word.startswith("pix2pix"):
    print('pix2pix')
    response = await multimedia.instruct_pix2pix(bot, file_ids, post)
  elif word.startswith("2x"):
    print('2x')
    response = await multimedia.upscale_image(bot, file_ids, post, 2)
  elif word.startswith("4x"):
    print('4x')
    response = await multimedia.upscale_image(bot, file_ids, post, 4)
  elif word.startswith("llm"):
    print('llm')
    response = await textgen_api.textgen_chat_completion(post['message'], {'internal': [], 'visible': []})
  elif word.startswith("storyteller"):
    print('storyteller')
    response = await multimedia.storyteller(bot, file_ids)
  elif word.startswith("summary"):
    print('summary')
    response = await multimedia.youtube_transcription(post['message'])
  else:
    return None
  return response

bot = mattermostdriver.Driver({'url':os.environ['MATTERMOST_URL'], 'token':os.environ['MATTERMOST_TOKEN'],'scheme':'https', 'port':443})
bot.login()
bot.init_websocket(context_manager)
