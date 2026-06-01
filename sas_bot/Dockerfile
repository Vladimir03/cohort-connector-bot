FROM node:20-slim AS frontend
WORKDIR /fe
COPY web/frontend/package.json web/frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /fe/dist/ ./web/static/
EXPOSE 8000
CMD ["python", "bot.py"]
