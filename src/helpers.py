from json import dumps
from math import ceil
from langdetect import detect_langs
from tiktoken import get_encoding

def count_image_tokens(w, h):
  return 85 + 170 * ceil(w/512) * ceil(h/512)

def count_tokens(msg):
  return len(get_encoding('cl100k_base').encode(dumps(msg)))

def mostly_english(context):
  probabilities = 0
  for text in [m['content'] for m in context]:
    for language in detect_langs(text):
      if language.lang == 'en':
        probabilities += language.prob
        break
  if probabilities / len(context) > 0.85:
    return True
  return False
