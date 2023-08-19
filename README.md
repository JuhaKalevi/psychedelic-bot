# Psychedelic Bot Project

This project is a Python-based Mattermost bot that is capable of handling posts in a Mattermost channel, performing various actions based on the content of the posts, and interacting with the OpenAI API for language generation tasks.

## Source Files

### psychedelic_bot.py

This Python code sets up a Mattermost bot that logs in, establishes a WebSocket connection to receive events, and handles new posts made by users. The code imports necessary modules and defines a context manager and a main function. The imported modules are `asyncio`, `json`, `log`, `mattermost_api`, and `mattermost_post_handler`.

### common.py

This Python script defines several functions for different tasks involving natural language processing and AI-powered language generation. It provides functions to count tokens in a message, generate a story based on image captions, and generate a summary of a YouTube video transcription.

### mattermost_post_handler.py

This Python code defines a class called `MattermostPostHandler`, which is responsible for handling posts in a Mattermost channel. The class contains several methods that perform various actions based on the content of the posts.

### textgen_api.py

This Python code defines an asynchronous function called `textgen_chat_completion`, which takes in a `message` and a `history` as parameters and returns a string. The function sends a POST request to a web API with a JSON payload, containing various parameters for generating a chat completion response.

### log.py

This Python code defines a function called `get_logger` that sets up a logger object using the `logging` module. It retrieves the log level value from the environment variable `LOG_LEVEL` and sets the log level of the logger using the obtained integer value.

### openai_api.py

This Python script defines several functions and variables for interacting with the OpenAI API. It includes functions for performing a chat completion using a specified model and messages, generating a response message based on the input message and available functions, and performing a streamed chat completion.

### mattermost_api.py

This Python code defines a class named `MattermostBot`, which inherits from `mattermostdriver.AsyncDriver`. The class contains several methods for interacting with the Mattermost API, such as creating or updating a post, creating a reaction to a post, checking if the bot's name is present in a message, and uploading files to a channel.

## Installation

1. Clone the repository.
2. Install the required Python packages.
3. Set the necessary environment variables, such as `TEXTGEN_WEBUI_URI` and `OPENAI_API_KEY`.
4. Run the `psychedelic_bot.py` script to start the bot.

## Usage

Once the bot is running, it will listen for new posts in the Mattermost channel and perform actions based on the content of the posts. It can generate language based on image captions, generate a summary of a YouTube video transcription, and perform various other tasks.