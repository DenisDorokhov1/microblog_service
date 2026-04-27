FROM python:3.12-slim

RUN apt-get update && apt-get install -y python3-dev supervisor nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /my_app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .

COPY ./dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/sites-available/default

RUN echo "#!/bin/bash\nnginx\nalembic upgrade head\nPYTHONPATH=. python3 -m uvicorn app.routes:app --host 127.0.0.1 --port 8000" > /my_app/run.sh

EXPOSE 80
CMD ["/bin/bash", "/my_app/run.sh"]