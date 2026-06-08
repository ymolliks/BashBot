FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 bashbot \
    && useradd -u 1000 -g bashbot -s /bin/sh -m bashbot

WORKDIR /BashBot
COPY . .
RUN pip install --no-cache-dir -r requirements.txt \
    && chown -R bashbot:bashbot /BashBot

USER bashbot
CMD [ "python", "./bashbot.py" ]
