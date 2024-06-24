FROM python
LABEL author="Gleb Tcivie"

WORKDIR /app
COPY requirements.txt .
COPY .env .
RUN pip3 install -r requirements.txt

COPY exporter/ exporter
COPY main.py .
CMD ["python3", "-u", "main.py"]