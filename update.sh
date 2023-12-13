#!/bin/bash -eu
. venv/bin/activate
pylint --jobs=$(nproc) src/*.py
systemctl --user restart psychedelic-bot@$SSH_ORIGINAL_COMMAND
