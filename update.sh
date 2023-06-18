#!/bin/bash
case "$SSH_ORIGINAL_COMMAND" in
  gpt-3.5-turbo-16k|gpt-4)
    git fetch --all
    git checkout $SSH_ORIGINAL_COMMAND
    git pull
    docker compose build
    docker compose up -d $SSH_ORIGINAL_COMMAND --force-recreate
    ;;
  *)
    echo Permission denied.
    exit 1
esac
