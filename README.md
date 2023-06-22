# Chatbot Program

This program is a chatbot that generates natural language responses based on user input and message context. It can understand and respond to various types of requests like generating images, interpreting non-English prompts, and generating appropriate text in replies.

## Dependencies

The following Python libraries need to be installed:

- `json`
- `os`
- `chardet`
- `langdetect`
- `mattermostdriver`
- `openai`
- `webuiapi`

Make sure to have the latest versions installed using `pip`:

```
pip install chardet langdetect mattermostdriver openai webuiapi
```

## Usage

1. Set up required environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `MATTERMOST_URL`: The URL for your Mattermost instance
   - `MATTERMOST_TOKEN`: Your Mattermost API token
   - `MATTERMOST_BOTNAME`: The bot's display name in Mattermost
   - `OPENAI_MODEL_NAME`: The OpenAI model to use (e.g., `gpt-4`)

2. Run the program:
```
python chatbot.py
```

3. The bot should now be active on Mattermost and generating responses based on user input.

## Features

This chatbot has the following features:

- Detects if a message requests image generation.
- Determines if a message asks for multiple images or just one.
- Checks if a text is mainly in English or other languages.
- Context-aware responses: provides relevant replies based on previous messages.
- Generates images from text prompts, handles non-English prompts, and professional terms.
- Handles errors from OpenAI and Mattermost APIs.

## License

MIT License.

### Note

Please note that the provided code is for informational purposes, do not use the code as-is without verification or validation. Always test and implement proper security measures.
