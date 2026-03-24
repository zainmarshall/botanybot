FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -U sciolyid

COPY botany_bot.py /app/botany_bot.py
COPY botany_data /app/botany_data

CMD ["python", "-u", "botany_bot.py"]
