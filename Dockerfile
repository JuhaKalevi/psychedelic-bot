FROM debian:trixie
#RUN apt-get update
#RUN apt-get -y install --no-install-recommends python3-dev python3-venv
WORKDIR /app
RUN python3 -m venv venv
RUN . venv/bin/activate
#RUN git clone https://github.com/Vaelor/python-mattermost-driver
#WORKDIR /app/python-mattermost-driver
#RUN pip install -r requirements.txt
#RUN python3 -u setup.py install
#WORKDIR /app
#RUN pip install -r requirements.txt
COPY *.py venv /app/
CMD python3 -u app.py
