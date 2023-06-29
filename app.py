# Import required modules
import json
import os
import chardet
import langdetect
import mattermostdriver
import openai
import webuiapi

# Set OpenAI's API 
openai.api_key = os.environ['OPENAI_API_KEY']

# Initialize the Mattermost Driver with the required information 
mm = mattermostdriver.Driver({
  'url': os.environ['MATTERMOST_URL'],
  'token': os.environ['MATTERMOST_TOKEN'],
  'port': 443
})

# Initialize the WebUI API and set its authentication
webui_api = webuiapi.WebUIApi(host=os.environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', os.environ['STABLE_DIFFUSION_WEBUI_API_KEY'])

# Function to check if a message is asking for image generation
def is_asking_for_image_generation(message):
  return generate_text_from_message(f'Is this a message where an image is probably requested? Answer only True or False: {message}') == 'True'

# Function to check if a message is asking for generating multiple images
def is_asking_for_multiple_images(message):
  return generate_text_from_message(f'Is this a message where multiple images are requested? Answer only True or False: {message}') == 'True'

# Function to check if a text is mainly in English
def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"

# Function to manage context of events
async def context_manager(event):
  file_ids = []
  event = json.loads(event)
  if 'event' in event and event['event'] == 'posted' and event['data']['sender_name'] != os.environ['MATTERMOST_BOTNAME']:
    post = json.loads(event['data']['post'])
    if post['root_id'] == "":
      if os.environ['MATTERMOST_BOTNAME'] not in post['message']:
        return
      thread_id = post['id']
      if is_asking_for_image_generation(post['message']):
        if is_asking_for_multiple_images(post['message']):
          openai_response_content = generate_images(post['message'], file_ids, post, 8)
        else:
          openai_response_content = generate_images(post['message'], file_ids, post, 1)
      else:
        context = {'order': [post['id']], 'posts': {post['id']: post}}
        openai_response_content = generate_text_from_context(context)
    else:
      thread_id = post['root_id']
      context = mm.posts.get_thread(post['id'])
      if not any(os.environ['MATTERMOST_BOTNAME'] in post['message'] for post in context['posts'].values()):
        return
      openai_response_content = generate_text_from_context(context)
    try:
      mm.posts.create_post(options={'channel_id':post['channel_id'], 'message':openai_response_content, 'file_ids':file_ids, 'root_id':thread_id})
    except (mattermostdriver.exceptions.InvalidOrMissingParameters, mattermostdriver.exceptions.ResourceNotFound) as err:
      print(f"Mattermost API Error: {err}")

# Function to fix image generation prompt
def fix_image_generation_prompt(prompt):
  return generate_text_from_message(f"convert this to english, in such a way that you are describing features of the picture that is requested in the message, starting from the most prominent features and you don't have to use full sentences, just a few keywords, separating these aspects by commas. Then after describing the features, add professional photography slang terms which might be related to such a picture done professionally: {prompt}")

# Function to generate images
def generate_images(user_prompt, file_ids, post, count):
  comment = ''
  # check if the main language is not english- if it isn't then fix the image generation prompt
  if not is_mainly_english(user_prompt.encode('utf-8')):
    comment = user_prompt = fix_image_generation_prompt(user_prompt)
  result = webui_api.txt2img(
    prompt = user_prompt,
    negative_prompt = "(unfinished:1.5), (sloppy and messy:1.5), (incoherent:1.5), (deformed:1.5)",
    steps = 42,
    sampler_name = 'UniPC',
    batch_size = count,
    restore_faces = True
  )
  # Save the generated image, then upload to the File Server and append the file id for Mattermost
  for image in result.images:
    image.save("result.png")
    with open('result.png', 'rb') as image_file:
      file_ids.append(mm.files.upload_file(post['channel_id'], files={'files': ('result.png', image_file)})['file_infos'][0]['id'])
  return comment

# Function to generate text from the context of a conversation
def generate_text_from_context(context):
  messages = []
  context['order'].sort(key=lambda x: context['posts'][x]['create_at'])
  for post_id in context['order']:
    if 'from_bot' in context['posts'][post_id]['props']:
      role = 'assistant'
    else:
      role = 'user'
    messages.append({'role': role, 'content': context['posts'][post_id]['message']})
  return openai_chat_completion(messages, os.environ['OPENAI_MODEL_NAME'])

# Function to generate text from a message
def generate_text_from_message(message, model='gpt-4'):
  return openai_chat_completion([{'role': 'user', 'content': message}], model)

# Function to create a conversation and return the result from OpenAI
def openai_chat_completion(messages, model='gpt-4'):
  try:
    openai_response_content = openai.ChatCompletion.create(model=model, messages=messages)['choices'][0]['message']['content']
  except (openai.error.APIConnectionError, openai.error.APIError, openai.error.AuthenticationError, openai.error.InvalidRequestError, openai.error.PermissionError, openai.error.RateLimitError, openai.error.Timeout) as err:
    openai_response_content = f"OpenAI API Error: {err}"
  return openai_response_content

# Logging in to the Mattermost driver
mm.login()

# Initialize the Mattermost's websocket and start listening to it
mm.init_websocket(context_manager)
