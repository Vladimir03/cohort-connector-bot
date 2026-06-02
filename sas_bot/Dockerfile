# Single-stage build. The React admin dashboard is pre-built and committed
# to web/static/, so there is no Node build step here — we just run the
# Python bot + FastAPI admin. (The old Node stage tried to COPY the frontend
# from /fe/dist/, but Vite outputs to ../static, so that build always failed.)
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "bot.py"]
