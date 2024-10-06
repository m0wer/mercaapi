FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./app /app/app
COPY ./main.py /app/main.py
COPY ./cli.py /app/cli.py
COPY ./alembic.ini /app/alembic.ini
COPY ./migrations/ /app/migrations
COPY ./static/ /app/static
