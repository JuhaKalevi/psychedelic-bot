import json
import os
import chardet
import langdetect
import mattermostdriver
import openai
import webuiapi

openai.api_key = os.environ['OPENAI_API_KEY']
mm = mattermostdriver.Driver({
  'url': os.environ['MATTERMOST_URL'],
  'token': os.environ['MATTERMOST_TOKEN'],
  'port': 443
})
webui_api = webuiapi.WebUIApi(host='kallio.psychedelic.fi', port=7860)
webui_api.set_auth('useri', 'passu')

def is_mainly_english(text):
  language = langdetect.detect(text.decode(chardet.detect(text)["encoding"]))
  return language == "en"

def openai_chat_completion(messages, model=os.environ['OPENAI_MODEL_NAME']):
  try:
    openai_response_content = openai.ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content

def generate_images(user_prompt, file_ids, post, count):
  comment = ''
  if not is_mainly_english(user_prompt.encode('utf-8')):
    comment = user_prompt = fix_image_generation_prompt(user_prompt)
  result = webui_api.txt2img(
    prompt = user_prompt,
    negative_prompt = "ugly, out of frame",
    steps = 42,
    sampler_name = 'UniPC',
    batch_size = count,
    restore_faces = True
  )
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
  return comment

def generate_text(context):
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
  return openai_chat_completion(messages)

def fix_image_generation_prompt(prompt):
  messages = [{'role': 'user', 'content': f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}"}]
  return openai_chat_completion(messages, 'gpt-4')

async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']:
    post = json.loads(event['data']['post'])
    if post['root_id'] == "":
      if os.environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      if post['message'].startswith('@generate-images'):
        openai_response_content = generate_images(post['message'].removeprefix('@generate-images'), file_ids, post, 8)
      elif post['message'].startswith('@generate-image'):
        openai_response_content = generate_images(post['message'].removeprefix('@generate-image'), file_ids, post, 1)
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text(context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(os.environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text(context)
    try:
      mm.posts.create_post(options={
        'channel_id': post['channel_id'],
        'message': openai_response_content,
        'file_ids': file_ids,
        'root_id': thread_id
      })
    except (mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f"Mattermost API Error: {err}")

mm.login()
mm.init_websocket(context_manager)
