FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN useradd --create-home flowboard && mkdir -p /app/data && chown -R flowboard:flowboard /app
USER flowboard
ENV HOST=0.0.0.0 PORT=8000 FLOWBOARD_DB=/app/data/flowboard.db PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "server.py"]
