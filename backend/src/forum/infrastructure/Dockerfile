FROM python:3.12

WORKDIR /src/

COPY backend/src/forum/infrastructure/requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

COPY backend/src/forum/. ./forum/
COPY backend/src/general/ ./general/

CMD ["bash", "forum/infrastructure/scripts/app.sh"]
