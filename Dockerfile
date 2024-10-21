FROM python:3.11-slim

RUN apt update \
    && apt install --no-install-recommends -y \
    ghostscript \
    tesseract-ocr-all \
    && rm -rf /var/lib/apt/lists/*
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

RUN useradd app && \
    chown -R app:app /app
USER app

COPY ./app /app/app
COPY ./main.py /app/main.py
COPY ./cli.py /app/cli.py
COPY ./alembic.ini /app/alembic.ini
COPY ./migrations/ /app/migrations
COPY ./static/ /app/static

CMD ["fastapi", "run", "main.py", "--port", "80", "--host", "0.0.0.0", "--workers", "4", "--proxy-headers"]
