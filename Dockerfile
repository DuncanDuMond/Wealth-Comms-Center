FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WEALTH_DB=/data/wealth.db
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY wealth_command_center ./wealth_command_center
COPY vendor ./vendor
COPY registry ./registry
COPY web ./web
RUN useradd --uid 10001 --create-home wealth && mkdir /data && chown wealth:wealth /data
USER wealth
VOLUME ["/data"]
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "wealth_command_center.app:app", "--host", "0.0.0.0", "--port", "8765", "--no-proxy-headers", "--no-access-log"]
