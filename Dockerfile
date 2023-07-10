FROM debian:trixie
WORKDIR /app
COPY *.py venv /app/
RUN . venv/bin/activate
CMD python3 -u app.py
