Добавить скрипт `start` в `package.json`.

**Что изменить:**
В блок `scripts` корневого `package.json` добавить строку:
```
"start": "node dist/server/index.mjs"
```

**Текущее состояние:** все остальные скрипты (`dev`, `build`, `build:dev`, `preview`, `lint`, `format`) уже присутствуют. Нужно только вставить `"start"` между `"build:dev"` и `"preview"`.