FROM python:3.12-slim

WORKDIR /app

ENV SCOREBOARD_BROWSER_ONLY=true
ENV SCOREBOARD_LISTENING_PORT=5000

COPY requirements-docker.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY start.py BLE.py ./
COPY static/ static/
COPY templates/ templates/

RUN mkdir -p results/temp

VOLUME ["/app/results"]

EXPOSE 5000

CMD ["python", "start.py"]
