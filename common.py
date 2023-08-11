import json
import os
import re
import gradio_client
import tiktoken
import openai_api

def count_tokens(message:str) -> int:
  return len(tiktoken.get_encoding('cl100k_base').encode(json.dumps(message)))

async def generate_story_from_captions(message:str, model='gpt-4') -> str:
  return await openai_api.chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)

async def generate_summary_from_transcription(message:str, model='gpt-4') -> str:
  return await openai_api.chat_completion([{
    'role': 'user',
    'content': (
      f"Summarize in appropriate detail, adjusting the summary length according to the transcription's length, the YouTube-video transcription below. IGNORE all advertisement(s), sponsorship(s), discount(s), promotions(s), etc. completely!"
      f" Also make a guess on how many different characters' speech is included in the transcription."
      f" Also analyze the style of this video (comedy, drama, instructional, educational, etc.)."
      f" Also give scoring 0-10 about the video for each of these categories: originality, difficulty, humor, boringness, creativity, artful."
      f" Transcription: {message}"
    )
  }], model)

async def youtube_transcription(message:str) -> str:
  input_str = message
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    gradio = gradio_client.Client(os.environ['TRANSCRIPTION_API_URI'])
    prediction = gradio.predict(message, fn_index=1)
    if 'error' in prediction:
      return f"ERROR gradio.predict(): {prediction['error']}"
    ytsummary = await generate_summary_from_transcription(prediction)
    return ytsummary
