FROM debian:bullseye
RUN apt-get update
RUN apt-get -y install --no-install-recommends curl gcc git jq python3-chardet python3-dev python3-langdetect python3-pip python3-venv python3-wheel
WORKDIR /app
RUN python3 -m venv venv
RUN . venv/bin/activate
RUN pip install mattermostdriver-asyncio openai tiktoken webuiapi
COPY *.py /app/
CMD python3 -u app.py
