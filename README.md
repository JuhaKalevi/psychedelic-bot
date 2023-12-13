# README for Psychedelic Bot

## Overview

Psychedelic Bot is an advanced integration for Discord and Mattermost platforms, designed to interact with users through natural language processing and various AI-driven functionalities. It can handle text and image-based requests, providing context-aware responses and actions.

## Features

- **Natural Language Understanding**: Interprets user messages and provides relevant responses.
- **Contextual Awareness**: Maintains conversation context for coherent interactions.
- **Image Analysis**: Analyzes images in conversation threads (Mattermost-specific).
- **Image Generation**: Generates images based on textual prompts (Mattermost-specific).
- **Weather Information**: Provides current weather updates based on location.
- **Self Code Analysis**: Analyzes its own code to ensure quality and adherence to standards.
- **Summary Generation**: Summarizes outside context information when requested.

## Prerequisites

- Python 3.8 or higher.
- Discord and Mattermost accounts with bot permissions.
- Access to OpenAI API.
- GitLab account with CI/CD pipeline capabilities.
- Server with SSH access for deployment.

## Installation

1. Clone the repository to your local machine or server.
2. Install the required Python dependencies by running `pip install -r requirements.txt`.
3. Set up environment variables for Discord and Mattermost API tokens, bot names, and other configuration details.

## Configuration

The bot requires several environment variables to be set:

- `DISCORD_TOKEN`: Token for Discord bot authentication.
- `MATTERMOST_TOKEN`: Token for Mattermost bot authentication.
- `MATTERMOST_URL`: URL of the Mattermost server.
- `MIDDLEWARE_URL`: URL for middleware services, such as image generation.
- `MIDDLEWARE_USERNAME` and `MIDDLEWARE_PASSWORD`: Credentials for middleware services.
- `WEATHERAPI_KEY`: API key for weather information service.
- `DISCORD_BOT_NAME` and `DISCORD_BOT_ID`: Name and ID for the Discord bot.
- `MATTERMOST_BOT_NAME`: Name for the Mattermost bot.

## Usage

Once configured, you can start the bot by running the `psychedelic_bot.py` script. The bot will automatically connect to the configured Discord and Mattermost servers and begin listening for messages.

## Deployment

The project includes a `.gitlab-ci.yml` file for setting up a GitLab CI/CD pipeline. The pipeline is configured to trigger an `update.sh` script via SSH, which should be set up on the deployment server to handle the deployment process.

### CI/CD Pipeline Setup

1. In your GitLab project, go to **Settings** > **CI / CD** and expand the **Variables** section.
2. Add all the necessary environment variables mentioned in the Configuration section.
3. Ensure that your server's SSH key is added to the GitLab project's **SSH Keys**.
4. Configure the `.gitlab-ci.yml` file to use the SSH key for connecting to the deployment server.

### Deployment Script

The `update.sh` script should perform the following actions:

1. Pull the latest code from the repository.
2. Install or update any necessary dependencies.
3. Restart the bot service to apply the new changes.

Make sure that the script is executable and configured as a restricted SSH command for security purposes.

## Contributing

Contributions to the Psychedelic Bot are welcome. Please ensure that you adhere to the project's coding standards and submit your pull requests to the repository for review.

## Support

For support, please open an issue in the project's GitLab repository. Our team will respond as soon as possible.

## License

The Psychedelic Bot is released under the [MIT License](LICENSE). Please review the license terms before using or contributing to the project.
