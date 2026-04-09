# app/Dockerfile

FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    if apt-cache show software-properties-common >/dev/null 2>&1; then \
        apt-get install -y software-properties-common; \
    else \
        echo "software-properties-common not available in this base image, skipping"; \
    fi && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/streamlit/streamlit-example.git .

COPY primer.xlsx /app
COPY requirements.txt /app
COPY streamlit_app.py /app
COPY calculations.py /app


RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
