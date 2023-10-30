#!/bin/bash -eu
. venv/bin/activate
pylint --jobs=8 src/*.py
systemctl --user restart psychedelic-bot@$SSH_ORIGINAL_COMMAND
