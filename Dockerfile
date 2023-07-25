FROM debian:bullseye
RUN apt-get update
RUN apt-get -y install --no-install-recommends g++ gcc git python3-dev python3-pip python3-venv
WORKDIR /app
RUN git clone https://github.com/Vaelor/python-mattermost-driver
WORKDIR /app/python-mattermost-driver
RUN pip install -r requirements.txt
RUN python3 -u setup.py install
WORKDIR /app
RUN python3 -m venv venv
RUN . venv/bin/activate
RUN pip install aiofiles chardet gradio_client langdetect mattermostdriver openai tiktoken webuiapi
COPY *.py requirements.txt /app/
CMD ["/usr/bin/python3", "-u", "psychedelic_bot.py"]
