import os
import json
import re
import aiofiles
import asyncio
import base64
import httpx
import bot
import gradio_client
import mattermost_api
import openai_api
import txt2txt

async def captioner(file_ids:list):
  captions = []
  async with httpx.AsyncClient() as client:
    for post_file_id in file_ids:
      file_response = mattermost_api.files.get_file(file_id=post_file_id)
      try:
        if file_response.status_code == 200:
          file_type = os.path.splitext(file_response.headers["Content-Disposition"])[1][1:]
          file_path_in_content = re.findall('filename="(.+)"', file_response.headers["Content-Disposition"])[0]
          post_file_path = f'{post_file_id}.{file_type}'
          async with aiofiles.open(post_file_path, 'wb') as post_file:
            await post_file.write(file_response.content)
          with open(post_file_path, 'rb') as perkele:
            img_byte = perkele.read()
          source_image_base64 = base64.b64encode(img_byte).decode("utf-8")
          data = {
            "forms": [
              {
                "name": "caption",
                "payload": {} # Additional form payload data should go here, based on spec
              }
            ],
            "source_image": source_image_base64, # Here is the base64 image
            "slow_workers": True
          }
          url = "https://stablehorde.net/api/v2/interrogate/async"
          headers = {"Content-Type": "application/json","apikey": "a8kMOjo-sgqlThYpupXS7g"}
          response = await client.post(url, headers=headers, data=json.dumps(data))
          response_content = response.json()
          await asyncio.sleep(15) # WHY IS THIS NECESSARY?!
          caption_res = await client.get('https://stablehorde.net/api/v2/interrogate/status/' + response_content['id'], headers=headers, timeout=420)
          caption = caption_res.json()['forms'][0]['result']['caption']
          captions.append(f"{file_path_in_content}: {caption}")
      except (RuntimeError, KeyError, IndexError) as err:
        captions.append(f"Error occurred while generating captions for file {post_file_id}: {str(err)}")
        continue
  return '\n'.join(captions)

async def generate_summary_from_transcription(message:dict, model='gpt-4'):
  response = await openai_api.chat_completion([
    {
      'role': 'user',
      'content': (f"Summarize in appropriate detail, adjusting the summary length"
        f" according to the transcription's length, the YouTube-video transcription below."
        f" Also make a guess on how many different characters' speech is included in the transcription."
        f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
        f" IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s),"
        f" all War Thunder/Athletic Green etc. talk completely. Also give scoring 0-10 about the video for each of these three categories: originality, difficulty, humor, boringness, creativity, artful, . Transcription: {message}")
    }
], model)
  return response

async def storyteller(post):
  captions = await captioner(post)
  story = await txt2txt.generate_story_from_captions(captions)
  return story

async def youtube_transcription(user_input:str) -> str:
  input_str = user_input
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    gradio = gradio_client.Client(os.environ['TRANSCRIPTION_API_URI'])
    prediction = gradio.predict(user_input, fn_index=1)
    if 'error' in prediction:
      return f"ERROR gradio.predict(): {prediction['error']}"
    ytsummary = await generate_summary_from_transcription(prediction)
    return bot._return(ytsummary)
