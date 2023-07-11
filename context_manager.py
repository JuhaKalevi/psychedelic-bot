from os import environ
from json import loads
from any2any import consider_image_generation, generate_text_from_context, generate_text_from_message, is_asking_for_channel_summary
from respond_to_magic_words import respond_to_magic_words
from mattermost_bot import channel_from_post, channel_context, create_post, should_always_reply, thread_context

async def context_manager(event:dict) -> None:
  file_ids = []
  event = loads(event)
  signal = None
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != environ['MATTERMOST_BOT_NAME']:
    post = loads(event['data']['post'])
    signal = await respond_to_magic_words(post, file_ids)
    if signal:
      await create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':post['root_id']})
    else:
      message = post['message']
      channel = await channel_from_post(post)
      always_reply = await should_always_reply(channel)
      if always_reply:
        reply_to = post['root_id']
        signal = await consider_image_generation(message, file_ids, post)
        if not signal:
          summarize = await is_asking_for_channel_summary(post)
          if summarize:
            context = await channel_context(post)
          else:
            context = await thread_context(post)
          signal = await generate_text_from_context(context, channel)
      elif environ['MATTERMOST_BOT_NAME'] in message:
        reply_to = post['root_id']
        context = await generate_text_from_message(message)
      else:
        reply_to = post['root_id']
        context = await thread_context(post)
        if any(environ['MATTERMOST_BOT_NAME'] in context_post['message'] for context_post in context['posts'].values()):
          signal = await generate_text_from_context(context, channel)
      if signal:
        await create_post(options={'channel_id':post['channel_id'], 'message':signal, 'file_ids':file_ids, 'root_id':reply_to})
