FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    musescore3 \
    default-jre \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/Audiveris/audiveris/releases/download/5.3.1/Audiveris_5.3.1.jar \
    -O /app/audiveris.jar

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "main.py"]
