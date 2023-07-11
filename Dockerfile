FROM debian:bullseye
RUN apt-get update
RUN apt-get -y install --no-install-recommends python3-dev python3-pip python3-venv
#RUN git clone https://github.com/Vaelor/python-mattermost-driver
#WORKDIR /app/python-mattermost-driver
#RUN pip install -r requirements.txt
#RUN python3 -u setup.py install
COPY *.py requirements.txt /app/
WORKDIR /app
RUN python3 -m venv venv
RUN . venv/bin/activate
RUN pip install -r requirements.txt
CMD python3 -u app.py
