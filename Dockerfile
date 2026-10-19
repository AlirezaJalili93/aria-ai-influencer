FROM python:3.11-slim

LABEL maintainer="Aria AI Influencer Project"
LABEL description="Standalone 24/7 Instagram AI Influencer Agent (Aria)"

WORKDIR /opt/aria-ai-influencer

# Install curl and timezone data
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Tehran
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python3", "instagram_ai_agent.py", "--run-daemon"]
