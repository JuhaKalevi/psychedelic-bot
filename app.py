from json import loads
from os import environ
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound
from mattermostdriver import Driver
import openai
import webuiapi

openai.api_key = environ['OPENAI_API_KEY']
mm = Driver({
  'url': environ['MATTERMOST_URL'],
  'token': environ['MATTERMOST_TOKEN'],
  'port': 443,
})
webui_api = webuiapi.WebUIApi(host='kallio.psychedelic.fi', port=7860)
webui_api.set_auth('useri', 'passu')

def generate_image(user_prompt, file_ids, post):
  result = webui_api.txt2img(
    prompt = user_prompt,
    negative_prompt = "ugly, out of frame",
    steps = 42,
    sampler_name = 'UniPC',
    batch_size = 8,
    n_iter = 13,
  )
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])

def generate_text(context):
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
  try:
    openai_response_content = openai.ChatCompletion.create(model=environ['OPENAI_MODEL_NAME'], messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content

async def context_manager(event):
  file_ids = []
  event = loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != environ['MATTERMOST_BOTNAME']:
    post = loads(event['data']['post'])
    if post['root_id'] == "":
      if environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      if post['message'].startswith('@generate-image'):
        generate_image(post['message'].removeprefix('@generate-image'), file_ids, post)
        openai_response_content = None
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text(context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text(context)
    try:
      mm.posts.create_post(options={
        'channel_id': post['channel_id'],
        'message': openai_response_content,
        'file_ids': file_ids,
        'root_id': thread_id
      })
    except (InvalidOrMissingParameters, ResourceNotFound) as err:
      print(f"Mattermost API Error: {err}")

mm.login()
mm.init_websocket(context_manager)
