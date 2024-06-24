FROM python:3.12-slim
LABEL author="Gleb Tcivie"

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .
CMD ["python3", "-u", "main.py"]