FROM python:3.10
WORKDIR /app
COPY shared/ /app/shared/
COPY services/catalog/ /app/
RUN pip install --no-cache-dir /app/shared && pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app:/app/shared
EXPOSE 5000
CMD ["python", "app.py"]
