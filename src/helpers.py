import base64
from json import dumps
from math import ceil
from tiktoken import get_encoding
import fitz

def base64_image_from_file(path):
  return base64.b64encode(open(path, 'rb').read()).decode("utf-8")

def base64_images_from_pdf_file(path):
  return [base64.b64encode(page.get_pixmap(matrix=fitz.Matrix(300/72,300/72)).tobytes('png')).decode('utf-8') for page in fitz.open(path)]

def count_image_tokens(w, h):
  return 85 + 170 * ceil(w/512) * ceil(h/512)

def count_tokens(msg):
  return len(get_encoding('cl100k_base').encode(dumps(msg)))
