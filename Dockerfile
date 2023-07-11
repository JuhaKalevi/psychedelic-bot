FROM debian:bullseye
RUN apt-get update
RUN apt-get install -y python3-wheel
WORKDIR /app
COPY *.py venv/ ./
RUN . venv/bin/activate
CMD python3 -u app.py
