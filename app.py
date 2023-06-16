from json import loads
from pathlib import Path
from os import environ
import mattermostdriver
import openai

code_files = []
  ".gitlab-ci.yml",
  "Dockerfile",
  "app.py",
  "docker-compose.yml",
  "update.sh",
]
code_keyword = "@self-analysis"
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
    for filename, file_path in code_files.items():
      with open(file_path, "r") as file:
        code = file.read()
      code_snippets.append(f"--- {filename} ---\n{code}\n")
    self_analysis = "```".join(code_snippets)
    print(self_analysis)
    context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
    messages = []
    for post_id in context['order']:
      if 'from_bot' in context['posts'][post_id]['props']:
        role = 'assistant'
      else:
        role = 'user'
      messages.append({'role': role, 'content': context['posts'][post_id]['message']})
    openai_response = openai.ChatCompletion.create(model=environ['OPENAI_MODEL_NAME'], messages=messages)
    mm.posts.create_post(options={
      'channel_id': post['channel_id'],
      'message': openai_response['choices'][0]['message']['content'],
      'file_ids': None,
      'root_id': thread_id
    })

mm.login()
mm.init_websocket(context_manager)
