# RemnaNode Checker Agent

Чекер для панели [RemnaNode-Checker](https://github.com/DuhastMish/RemnaNode-Checker): лёгкий контейнер,
который ставится в ту сеть, **из которой** нужно проверять ноды (дом, мобильная сеть, дата-центр) — на отдельную машину, не на машину панели.
Забирает у панели список нод, проверяет их (SSH и прокси) и отправляет результаты обратно.

- Только исходящие соединения: белый IP и открытые порты не нужны, за NAT работает.
- Список нод и конфиг — только в памяти, на диск ничего не пишется. Адреса нод в логи не попадают.
- Python, только стандартная библиотека. Образ: `linux/amd64`, `linux/arm64`, `linux/arm/v7`.

## Запуск

1. В панели: **Чекеры → Добавить**, введите имя. Панель один раз покажет готовую команду.
2. Выполните её на машине чекера (нужен Docker: `curl -fsSL https://get.docker.com | sh`):

```bash
docker run -d --name nodecheck-agent --restart unless-stopped \
  ghcr.io/duhastmish/remnanode-checker-agent:latest admin.example.com nck_…
```

Аргументы: домен панели (это `https://admin.example.com`) и токен чекера. Больше ничего настраивать
не нужно — параметры проверок чекер получает от панели.

`--restart unless-stopped` — чтобы чекер поднимался после перезагрузки машины: у `docker run` политику
перезапуска нельзя зашить в образ. В `docker-compose.yml` она уже прописана.

Логи: `docker logs -f nodecheck-agent`. В течение минуты появится `подключён к панели`, затем сводка
`плановая проверка: N целей … отправлено N`.

### docker compose

```bash
curl -fsSLO https://raw.githubusercontent.com/DuhastMish/RemnaNode-Checker-Agent/main/docker-compose.yml
PANEL_URL=admin.example.com CHECKER_TOKEN=nck_… docker compose up -d
```

Или положите `PANEL_URL` и `CHECKER_TOKEN` в `.env` рядом с `docker-compose.yml`.

## Обновление

```bash
docker pull ghcr.io/duhastmish/remnanode-checker-agent:latest
docker rm -f nodecheck-agent
docker run -d --name nodecheck-agent --restart unless-stopped \
  ghcr.io/duhastmish/remnanode-checker-agent:latest admin.example.com nck_…
```

Токен запущенного чекера: `docker inspect nodecheck-agent --format '{{.Args}}'`. Если потерян —
**Перевыпустить токен** в панели (старый перестанет работать).

## Параметры

| Что | Описание |
|---|---|
| 1-й аргумент | домен панели (`admin.example.com` → `https://…`) или полный адрес |
| 2-й аргумент | токен чекера `nck_…` |
| `PANEL_URL`, `CHECKER_TOKEN` | то же через окружение (для compose), если аргументов нет |
| `ALLOW_HTTP=1` | разрешить `http://` к панели в доверенной локальной сети (токен идёт открытым текстом) |

## Ошибки

| Сообщение в логе | Что делать |
|---|---|
| `панель отклонила токен (401)` | ключ скопирован не полностью или токен перевыпущен |
| `(403)` | чекер отключён в панели |
| `адрес панели должен быть https://` | передайте домен панели, а не `http://IP:порт`; в LAN — `-e ALLOW_HTTP=1` |
| `панель недоступна` | DNS/HTTPS до панели с этой машины: `curl -I https://admin.example.com` |

## Сборка

Образ собирается GitHub Actions ([.github/workflows/docker.yml](.github/workflows/docker.yml)) и
публикуется в GHCR: `latest` — с ветки `main`, `X.Y.Z` / `X.Y` — с тегов `vX.Y.Z`.

Локально:

```bash
docker build -t nodecheck-agent .
docker run --rm nodecheck-agent admin.example.com nck_…
```
