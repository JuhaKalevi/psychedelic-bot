from os import environ
from webuiapi import WebUIApi

webui_api = WebUIApi(host=environ['STABLE_DIFFUSION_WEBUI_HOST'], port=7860)
webui_api.set_auth('psychedelic-bot', environ['STABLE_DIFFUSION_WEBUI_API_KEY'])
