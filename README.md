# Psychedelic Bot

A Conversational AI Bot via OpenAI GPT-4 and Custom Text Generation API 

This is a cloud-based conversational AI implementation using OpenAI's GPT-4 model and a custom text generation API. It also includes capabilities of processing image related operations. 

## Getting Started

These instructions will help you set up the project on your local machine.

## Prerequisites

- Python 3.6 or later.
- Python libraries - `json`, `os`, `requests`, `PIL`, `chardet`, `langdetect`, `mattermostdriver`, `OpenAI`, `webuiapi`.

## Structure

The project is divided into four main Python files:

1. `api_connections.py`
2. `app.py`
3. `image_processing.py`
4. `language_processing.py`

#### api_connections.py

Here we establish connections with different APIs including `OpenAI`, `Mattermost`, and `webuiapi`. Included are functions to send request and receive response from OpenAI and custom text generation API models.

#### app.py

The central application file that signs into your chat interface (here, Mattermost) and listens for new events, reacting accordingly with either text or image responses.

#### image_processing.py

Contains methods for processing image-centric commands, including image generation and image upscaling using the `webuiapi`.

#### language_processing.py

A file defining core language and text processing functions that facilitate communication between the AI and the user.

## Setup

Remember to set the environment variables with your respective API keys.

## Running

You can start the application by running `app.py`.

## Built With

- [OpenAI](https://openai.com/research/)
- [Mattermostdriver](https://pypi.org/project/mattermostdriver/)
- [webuiapi](https://link-to-web-ui-api-provider.com)

## Contributing

TODO

## Versioning

TODO

## Authors

- bunnyh, ronaz

## License

This project is licensed under the IDC (I don't care) License - use your brains for details.

## Acknowledgments

- OpenAI's team
- The creator of Stable Diffusion
- Anyone whose code was used \o/
