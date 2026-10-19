FROM python:3.11-slim

LABEL maintainer="Aria AI Influencer Project"
LABEL description="Standalone 24/7 Instagram AI Influencer Agent (Aria)"

WORKDIR /opt/aria-ai-influencer

# FriBiDi is loaded at runtime by Pillow's vendored Raqm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    libfribidi0 \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Tehran
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python3 scripts/check_typography.py

EXPOSE 8080

CMD ["python3", "instagram_ai_agent.py", "--run-daemon"]
