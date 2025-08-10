FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache curl

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY listener.py /app/

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080
CMD ["python", "listener.py"]
