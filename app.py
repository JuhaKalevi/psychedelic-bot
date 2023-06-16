from json import loads
from os import environ
import mattermostdriver
import openai

code_files = [
  "app.py",
  "docker-compose.yml",
  "Dockerfile",
  ".gitlab-ci.yml",
  ".pylintrc",
  "update.sh",
]
code_snippets = []
openai.api_key = environ['OPENAI_API_KEY']

mm = mattermostdriver.Driver({
  'url': environ['MATTERMOST_URL'],
  'token': environ['MATTERMOST_TOKEN'],
  'port': 443,
})

async def context_manager(event):
  event = loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != environ['MATTERMOST_BOTNAME']:
    post = loads(event['data']['post'])
    if post['root_id'] == "":
      if environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      context = {'order': [post['id']], 'posts': {post['id']: post}}
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
    for file_path in code_files:
      with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()
      code_snippets.append(f"--- {file_path} ---\n{code}\n")
    messages = [{'role':'user', 'content':'This is your code. Abstain from posting parts of your code unless discussing changes to them.'+'```'.join(code_snippets)}]
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
    for post_id in context['order']:
      if 'from_bot' in context['posts'][post_id]['props']:
        role = 'assistant'
      else:
        role = 'user'
      messages.append({'role':role, 'content':context['posts'][post_id]['message']})
    openai_response = openai.ChatCompletion.create(model=environ['OPENAI_MODEL_NAME'], messages=messages)
    mm.posts.create_post(options={
      'channel_id': post['channel_id'],
      'message': openai_response['choices'][0]['message']['content'],
      'file_ids': None,
      'root_id': thread_id
    })

mm.login()
mm.init_websocket(context_manager)
