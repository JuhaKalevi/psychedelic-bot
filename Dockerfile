FROM debian:trixie
WORKDIR /app
RUN . venv/bin/activate
COPY *.py venv /app/
CMD python3 -u app.py
