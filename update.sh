#!/bin/bash
case "$SSH_ORIGINAL_COMMAND" in
  gpt-3.5-turbo-16k)
    git fetch --all
    git checkout $SSH_ORIGINAL_COMMAND
    git pull
    docker compose pull
    docker compose up -d $SSH_ORIGINAL_COMMAND
    docker pull gitlab.psychedelic.fi:5050/ai/bots/psychedelic-bot:latest
    docker run -d gitlab.psychedelic.fi:5050/ai/bots/psychedelic-bot:latest
    ;;
  *)
    echo Permission denied.
    exit 1
esac
