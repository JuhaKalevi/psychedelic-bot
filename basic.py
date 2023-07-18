import chardet
import langdetect
import openai_api

async def generate_story_from_captions(message, model='gpt-4'):
  return await openai_api.chat_completion([{'role':'user', 'content':(f"Make a consistent story based on these image captions: {message}")}], model)

async def generate_summary_from_transcription(message, model='gpt-4'):
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

async def is_mainly_english(text):
  return langdetect.detect(text.decode(chardet.detect(text)["encoding"])) == "en"
