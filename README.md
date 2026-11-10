# Scope Cinemas ticket watcher

Checks a movie page every 5 minutes and sends an email + WhatsApp message
the moment the **BUY TICKETS** button shows up in the hero banner.

It only looks at the hero section at the top of the page. The "You may also
like" carousel lower down has Buy Tickets buttons for *other* movies, so a
plain "page contains Buy Tickets" check would give a false alarm right away.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill it in
```

**Gmail:** turn on 2-Step Verification, then create an App Password
(Google Account → Security → App passwords) and put it in `SMTP_PASS`.

**Telegram (recommended):** in Telegram, chat with @BotFather → `/newbot` →
pick a name → copy the token into `TELEGRAM_BOT_TOKEN`. Open your new bot,
press **Start**, then run `python monitor.py --telegram-chat-id` and copy the
printed line into `.env`.

**WhatsApp (optional, CallMeBot, free — often full):** save CallMeBot's number in your contacts and
send it the activation message shown on callmebot.com (WhatsApp section).
It replies with your API key → put it in `CALLMEBOT_APIKEY`.
Prefer something more official? Set `WHATSAPP_PROVIDER=twilio` and use the
Twilio WhatsApp sandbox.

Test both channels:

```bash
python monitor.py --test-notify
```

## Run

```bash
python monitor.py                         # uses WATCH_URLS from .env
python monitor.py https://www.scopecinemas.com/movies/some-other-movie
python monitor.py URL1 URL2 --interval 180
python monitor.py --once                  # single check (good for cron)
```

It stops after it has alerted for every URL (add `--keep-running` to keep going).
Alerts are recorded in `watch_state.json`, so a restart won't re-send them —
delete that file to reset.

If the page can't be read for ~1 hour (site down, blocked, layout changed),
you also get a "can't read the page" alert so it never fails silently.

## Keep it running 24/7

Pick one:

- **Raspberry Pi / VPS / always-on PC:** use `ticket-watch.service` (instructions inside the file).
- **Quick and dirty:** `nohup python monitor.py > watch.log 2>&1 &`
- **Cron instead of a loop:** `*/5 * * * * cd /path/to/ticket-watch && .venv/bin/python monitor.py --once`

## Tests

```bash
pip install pytest && pytest -q
```
