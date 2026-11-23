FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY manage.py .
COPY entrypoint.py .
RUN useradd --create-home energy && mkdir -p /app/models_cache && chown energy:energy /app/models_cache
USER energy
EXPOSE 8000
CMD ["python", "entrypoint.py"]
