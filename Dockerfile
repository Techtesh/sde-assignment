FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
ENTRYPOINT ["bash", "./run.sh"]
