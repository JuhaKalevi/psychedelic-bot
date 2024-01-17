import base64
from json import dumps
from math import ceil
import numpy
import cv2
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

def crop_borders(base64_image, threshold):
  print(base64_image)
  img = cv2.imdecode(numpy.frombuffer(base64.b64decode(base64_image), dtype=numpy.uint8), cv2.IMREAD_UNCHANGED)
  _, binarized = cv2.threshold(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), threshold, 255, cv2.THRESH_BINARY_INV)
  contours, _ = cv2.findContours(binarized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
  _, encoded_img = cv2.imencode('.png', img[y:y+h, x:x+w])
  print(base64.b64encode(encoded_img).decode('utf-8'))
  return base64.b64encode(encoded_img).decode('utf-8')
