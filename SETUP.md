## run

```
pip install -r requirements.txt --break-system-packages
python3 main.py
```

## env vars (.env or export before running)

- `BOT_TOKEN` — from @BotFather
- `BOT_USERNAME` — no @ (Xtickerzbot)
- `ADMIN_IDS` — comma-separated telegram user ids
- `LOG_CHANNEL_ID` — channel id the bot is admin of, for logs (optional)
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` — from upstash.com
- `PENDING_JOB_TTL` — seconds a crop/preview job stays valid (default 600)

force-sub channel (@xtickerz by default), start text/image, and rate limit
are NOT env vars — they're admin-editable at runtime via /settings, stored
in redis. add the bot as admin in @xtickerz or force-sub silently no-ops.

## admin commands

- `/ban <id>` / `/unban <id>`
- `/stats` — sticker count
- `/health` — ffmpeg / redis / disk check
- `/broadcast <text>` — sends to every chat that has ever messaged the bot
- `/settings` — view current start text/image, force-sub channel, rate limit
- `/setstarttext <text>`
- `/setstartimage` — reply to a photo (or `/setstartimage none` to clear)
- `/setforcesub <@channel|off>`
- `/setratelimit <n>`
- `/resetsettings` — wipes all of the above back to hardcoded defaults

## user commands

- `/newpack <name>`, `/usepack <name>`, `/mypacks`
- `/renamepack <name> <new title>` — own packs only, admins can rename any
- `/removesticker` — reply to a sticker with this to pull it from its pack

## keep it alive on a VPS

systemd unit (`/etc/systemd/system/stickerbot.service`):

```
[Unit]
Description=sticker bot
After=network.target

[Service]
WorkingDirectory=/path/to/xtickerzbot
EnvironmentFile=/path/to/xtickerzbot/.env
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```
systemctl enable --now stickerbot
```
