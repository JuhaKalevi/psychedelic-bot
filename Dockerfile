FROM debian:bullseye
RUN apt-get update
RUN apt-get -y install --no-install-recommends curl gcc git jq python3-chardet python3-dev python3-langdetect python3-pip python3-venv python3-wheel
WORKDIR /app
RUN python3 -m venv venv
RUN . venv/bin/activate
RUN git clone https://github.com/Vaelor/python-mattermost-driver
WORKDIR /app/python-mattermost-driver
RUN pip install -r requirements.txt
RUN python3 -u setup.py install
WORKDIR /app
RUN pip install openai tiktoken webuiapi gradio_client aiofiles httpx
COPY *.py /app/
CMD python3 -u app.py
