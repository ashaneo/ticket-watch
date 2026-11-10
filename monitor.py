#!/usr/bin/env python3
"""
Scope Cinemas ticket watcher.

Polls one or more movie pages and alerts you (email + WhatsApp) the moment
the hero "BUY TICKETS" button appears.

Detection is scoped to the hero <header> inside <main>, because the
"YOU MAY ALSO LIKE" carousel further down the page contains "Buy Tickets"
buttons for *other* movies. A naive "does the page contain Buy Tickets"
check would fire immediately on a false positive.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:  # optional: load settings from a .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("ticket-watch")

DEFAULT_URL = "https://www.scopecinemas.com/movies/avengers-doomsday"
BUY_LABEL = re.compile(r"^\s*buy tickets?\b", re.I)
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def check_html(html: str) -> tuple[bool | None, str]:
    """
    Returns (available, title).
    available is True/False, or None when the page doesn't look like a movie
    page (blocked by Cloudflare, layout changed, error page, ...).
    """
    soup = BeautifulSoup(html, "html.parser")
    # The site streams with Next.js: the raw HTML first has a *loading* <main>
    # (logo + progress bar), and the real page sits in a later hidden block.
    # So look through every <main> for the one whose <header> has the title.
    hero = None
    for main in soup.find_all("main"):
        header = main.find("header")
        if header and header.find("h1"):
            hero = header
            break
    if hero is None:
        page_title = soup.title.get_text(strip=True) if soup.title else "no <title>"
        return None, f"hero section not found (page title: {page_title!r}, {len(html)} bytes)"

    h1 = hero.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else "Unknown movie"

    for el in hero.find_all(["button", "a"]):
        label = el.get("aria-label") or ""
        text = el.get_text(" ", strip=True)
        if BUY_LABEL.match(label) or BUY_LABEL.fullmatch(text):
            return True, title
    return False, title


def fetch(url: str, timeout: int = 25) -> str:
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# --------------------------------------------------------------------------- #
# Notifiers
# --------------------------------------------------------------------------- #
def send_email(subject: str, body: str) -> bool:
    host, user, password, to = (
        env("SMTP_HOST", "smtp.gmail.com"),
        env("SMTP_USER"),
        env("SMTP_PASS"),
        env("EMAIL_TO"),
    )
    if not (user and password and to):
        log.warning("Email not configured (SMTP_USER / SMTP_PASS / EMAIL_TO); skipping")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = env("EMAIL_FROM", user)
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(env("SMTP_PORT", "587")), timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        log.info("Email sent to %s", to)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Email failed: %s", exc)
        return False


def send_whatsapp(text: str) -> bool:
    provider = (env("WHATSAPP_PROVIDER", "callmebot") or "").lower()
    to = env("WHATSAPP_TO")  # international format, e.g. +94771234567
    if not to:
        log.warning("WhatsApp not configured (WHATSAPP_TO); skipping")
        return False
    try:
        if provider == "callmebot":
            apikey = env("CALLMEBOT_APIKEY")
            if not apikey:
                log.warning("CALLMEBOT_APIKEY missing; skipping WhatsApp")
                return False
            r = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": to, "text": text, "apikey": apikey},
                timeout=30,
            )
        elif provider == "twilio":
            sid, token = env("TWILIO_ACCOUNT_SID"), env("TWILIO_AUTH_TOKEN")
            sender = env("TWILIO_WHATSAPP_FROM", "+14155238886")  # Twilio sandbox
            if not (sid and token):
                log.warning("Twilio credentials missing; skipping WhatsApp")
                return False
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"From": f"whatsapp:{sender}", "To": f"whatsapp:{to}", "Body": text},
                auth=(sid, token),
                timeout=30,
            )
        else:
            log.error("Unknown WHATSAPP_PROVIDER %r (use callmebot or twilio)", provider)
            return False
        r.raise_for_status()
        log.info("WhatsApp sent to %s via %s", to, provider)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("WhatsApp failed: %s", exc)
        return False


def send_telegram(text: str) -> bool:
    token, chat_id = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        log.info("Telegram not configured; skipping")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"},
            timeout=30,
        )
        r.raise_for_status()
        log.info("Telegram sent")
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Telegram failed: %s", exc)
        return False


def print_telegram_chat_id() -> int:
    """Helper: message your bot once, then run --telegram-chat-id to see your chat id."""
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in .env first.")
        return 1
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
    r.raise_for_status()
    chats = {
        (u.get("message") or {}).get("chat", {}).get("id"): (u.get("message") or {}).get("chat", {}).get("first_name")
        for u in r.json().get("result", [])
    }
    chats.pop(None, None)
    if not chats:
        print("No messages found. Open your bot in Telegram, press Start / send 'hi', then run this again.")
        return 1
    for cid, name in chats.items():
        print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
    return 0


def notify(subject: str, body: str) -> None:
    text = f"{subject}\n\n{body}"
    send_email(subject, body)
    send_telegram(text)
    if env("WHATSAPP_TO"):
        send_whatsapp(text)


# --------------------------------------------------------------------------- #
# State (so a restart doesn't re-send alerts)
# --------------------------------------------------------------------------- #
class State:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self.data = {}

    def get(self, url: str) -> dict:
        return self.data.setdefault(url, {"notified": False, "failures": 0, "fail_alerted": False})

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2))


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def check_url(url: str, st: dict, fail_alert_after: int) -> tuple[bool | None, str]:
    try:
        available, title = check_html(fetch(url))
    except Exception as exc:  # noqa: BLE001
        available, title = None, f"fetch error: {exc}"

    if available is None:
        st["failures"] += 1
        log.warning("%s -> could not check (%s) [%d in a row]", url, title, st["failures"])
        if st["failures"] >= fail_alert_after and not st["fail_alerted"]:
            notify(
                "Ticket watcher can't read the page",
                f"{url}\nFailed {st['failures']} checks in a row. Last error: {title}\n"
                "The site may be blocking the bot or the layout changed.",
            )
            st["fail_alerted"] = True
        return available, title

    st["failures"], st["fail_alerted"] = 0, False
    if available:
        log.info("%s -> TICKETS AVAILABLE for %s", url, title)
        if not st["notified"]:
            notify(f"🎟️ Tickets are OUT: {title}", f"Buy Tickets button is live.\nBook now: {url}")
            st["notified"] = True
    else:
        log.info("%s -> not yet (%s)", url, title)
    return available, title


def send_status_email(results: list[tuple[str, bool | None, str]]) -> None:
    """Daily 'how are things' email, sent whether tickets are out or not."""
    icon = {True: "🎟️ TICKETS OUT", False: "⏳ Not yet", None: "⚠️ Couldn't check"}
    lines = [f"{icon[a]} — {t}\n{u}" for u, a, t in results]
    if any(a is True for _, a, _ in results):
        subject = "Ticket status: 🎟️ TICKETS ARE OUT"
    elif any(a is None for _, a, _ in results):
        subject = "Ticket status: ⚠️ couldn't check the page"
    else:
        subject = "Ticket status: ⏳ not yet"
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    send_email(subject, "\n\n".join(lines) + f"\n\nChecked at {stamp}. The watcher is still running.")


def main() -> int:
    p = argparse.ArgumentParser(description="Watch Scope Cinemas pages for ticket sales.")
    p.add_argument("urls", nargs="*", help="Movie page URL(s). Default: WATCH_URLS env or Avengers: Doomsday")
    p.add_argument("--interval", type=int, default=int(env("CHECK_INTERVAL", "300")), help="Seconds between checks (default 300)")
    p.add_argument("--once", action="store_true", help="Run one check and exit")
    p.add_argument("--keep-running", action="store_true", help="Keep watching after tickets are found")
    p.add_argument("--test-notify", action="store_true", help="Send a test email + WhatsApp and exit")
    p.add_argument("--state", default=env("STATE_FILE", "watch_state.json"))
    p.add_argument("--telegram-chat-id", action="store_true", help="Print your Telegram chat id and exit")
    p.add_argument("--status", action="store_true", help="Also email the current status, tickets or not (daily digest)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.telegram_chat_id:
        return print_telegram_chat_id()

    if args.test_notify:
        notify("Ticket watcher test", "If you got this, notifications are working.")
        return 0

    urls = args.urls or [u.strip() for u in (env("WATCH_URLS", DEFAULT_URL) or "").split(",") if u.strip()]
    fail_alert_after = int(env("FAIL_ALERT_AFTER", "12"))  # 12 x 5 min = 1 hour
    state = State(Path(args.state))
    log.info("Watching %d URL(s) every %ds: %s", len(urls), args.interval, ", ".join(urls))

    while True:
        results = []
        for url in urls:
            available, title = check_url(url, state.get(url), fail_alert_after)
            results.append((url, available, title))
        state.save()
        if args.status:
            send_status_email(results)

        if args.once:
            done = all(state.get(u)["notified"] for u in urls)
            gh_out = os.getenv("GITHUB_OUTPUT")
            if gh_out:  # lets the GitHub workflow disable itself once alerted
                with open(gh_out, "a") as f:
                    f.write(f"all_notified={'true' if done else 'false'}\n")
            return 0
        if not args.keep_running and all(state.get(u)["notified"] for u in urls):
            log.info("Tickets found for every URL; stopping. Use --keep-running to keep watching.")
            return 0
        time.sleep(args.interval + random.uniform(0, 15))  # small jitter


if __name__ == "__main__":
    sys.exit(main())
