from datetime import datetime
from json import loads
from os import environ
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound
from mattermostdriver import Driver
import openai
import webuiapi

code_files = [
  "app.py",
  "docker-compose.yml",
  "Dockerfile",
  ".gitlab-ci.yml",
  "update.sh",
]
openai.api_key = environ['OPENAI_API_KEY']
mm = Driver({
  'url': environ['MATTERMOST_URL'],
  'token': environ['MATTERMOST_TOKEN'],
  'port': 443,
})
webui_api = webuiapi.WebUIApi(host='kallio.psychedelic.fi', port=7860)
webui_api.set_auth('useri', 'passu')

def generate_image(user_prompt):
  result = webui_api.txt2img(prompt=user_prompt, negative_prompt="ugly, out of frame")
  result.image.save("result.png")

def generate_text(user_post, context):
  code_snippets = []
  messages = []
  if '@code-analysis' in user_post:
    for file_path in code_files:
      with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
      code_snippets.append(f"--- {file_path} ---\n{code}\n")
    messages.append({'role':'system', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them. Use 2 spaces for indentation and try to keep it minimalistic!'+'```'.join(code_snippets)})
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    post_username = mm.users.get_user(context['posts'][post_id]['user_id'])['username']
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
      messages.append({'role': 'user', 'content': f'The following message is from user named {post_username}, timestamp '+str(datetime.fromtimestamp(context['posts'][post_id]['create_at']/1000).strftime("%Y-%m-%d %H:%M"))})
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
    print(context['posts'][post_id]['message'])
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
        generate_image(post['message'].removeprefix('@generate-image'))
        with open('result.png', 'rb') as image_file:
          file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
        openai_response_content = "Here is the generated image:"
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text(post, context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text(post, context)
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
