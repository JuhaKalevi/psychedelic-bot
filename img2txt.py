from asyncio import sleep
from base64 import b64encode
from json import dumps
from os import path
import re
from httpx import AsyncClient
import aiofiles
from bot import get_mattermost_file
from txt2txt import generate_story_from_captions

async def captioner(file_ids:list) -> str:
  captions = []
  async with AsyncClient() as client:
    for post_file_id in file_ids:
      file_response = get_mattermost_file(post_file_id)
      try:
        if file_response.status_code == 200:
          file_type = path.splitext(file_response.headers["Content-Disposition"])[1][1:]
          file_path_in_content = re.findall('filename="(.+)"', file_response.headers["Content-Disposition"])[0]
          post_file_path = f'{post_file_id}.{file_type}'
          async with aiofiles.open(post_file_path, 'wb') as post_file:
            await post_file.write(file_response.content)
          with open(post_file_path, 'rb') as perkele:
            img_byte = perkele.read()
          source_image_base64 = b64encode(img_byte).decode("utf-8")
          data = {'forms':[{'name':'caption','payload':{}}], 'source_image':source_image_base64, 'slow_workers':True}
          url = 'https://stablehorde.net/api/v2/interrogate/async'
          headers = {"Content-Type": "application/json","apikey": "a8kMOjo-sgqlThYpupXS7g"}
          response = await client.post(url, headers=headers, data=dumps(data))
          response_content = response.json()
          await sleep(15) # WHY IS THIS NECESSARY?!
          caption_res = await client.get('https://stablehorde.net/api/v2/interrogate/status/' + response_content['id'], headers=headers, timeout=420)
          caption = caption_res.json()['forms'][0]['result']['caption']
          captions.append(f'{file_path_in_content}: {caption}')
      except (RuntimeError, KeyError, IndexError) as err:
        captions.append(f'Error occurred while generating captions for file {post_file_id}: {str(err)}')
        continue
  return '\n'.join(captions)

async def storyteller(post:dict) -> str:
  captions = await captioner(post)
  story = await generate_story_from_captions(captions)
  return story
