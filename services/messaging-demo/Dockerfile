FROM python:3.10
EXPOSE 5000
WORKDIR /app
COPY shared/ /app/shared/
COPY services/messaging-demo/ /app/
RUN pip install --no-cache-dir /app/shared && pip install --no-cache-dir -r requirements.txt
ENV PYTHONPATH=/app:/app/shared
CMD ["python", "app.py"]
