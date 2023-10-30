#!/bin/bash -eu
echo "Deploying $SSH_ORIGINAL_COMMAND"
cd $SSH_ORIGINAL_COMMAND
git pull
. venv/bin/activate
pylint --jobs=8 src/*.py
systemctl --user restart psychedelic-bot@$SSH_ORIGINAL_COMMAND
