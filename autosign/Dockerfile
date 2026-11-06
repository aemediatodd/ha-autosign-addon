FROM python:3.13-alpine
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apk add --no-cache tzdata ca-certificates && pip install --no-cache-dir requests==2.32.5 rsa==4.9.1
WORKDIR /app
COPY app/ /app/
CMD ["python", "server.py"]
