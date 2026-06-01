## Что сделать

1. Найти запущенные процессы бота в sandbox:
   ```
   pgrep -af "python.*bot.py"
   ```
2. Убить их:
   ```
   pkill -f "python.*bot.py" || true
   ```
3. Проверить, что ничего не слушает 8000 и нет живого `bot.py`:
   ```
   pgrep -af "bot.py"; lsof -i :8000 || true
   ```
4. Убить cloudflared-туннель (он больше не нужен — админка переедет на Railway-домен):
   ```
   pkill -f cloudflared || true
   ```

## Результат

- В sandbox не остаётся ни одного `python bot.py` — Telegram перестаёт получать конкурирующие `getUpdates`, ошибка `Conflict: terminated by other getUpdates request` исчезает.
- Railway-инстанс становится единственным polling-клиентом.
- Cloudflared-ссылка перестаёт работать — это ожидаемо, новая админка будет по Railway-домену.

## Чего НЕ делаю

- Не трогаю код (`handlers.py`, `bot.py`, `scheduler.py` и т.д.).
- Не меняю `.env`, `requirements.txt`, Dockerfile.
- Ничего не деплою и не пушу.
