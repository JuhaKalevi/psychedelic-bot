FROM debian:trixie
WORKDIR /app
COPY *.py venv/ ./
RUN . venv/bin/activate
CMD python3 -u app.py
