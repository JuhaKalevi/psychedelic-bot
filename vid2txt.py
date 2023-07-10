from os import environ
import re
from gradio_client import Client as GradioClient
from txt2txt import generate_summary_from_transcription

async def youtube_transcription(user_input:str) -> str:
  input_str = user_input
  url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
  urls = re.findall(url_pattern, input_str)
  if urls:
    gradio = GradioClient(environ['TRANSCRIPTION_API_URI'])
    prediction = gradio.predict(user_input, fn_index=1)
    if 'error' in prediction:
      return f"ERROR gradio.predict(): {prediction['error']}"
    ytsummary = await generate_summary_from_transcription(prediction)
    return ytsummary
