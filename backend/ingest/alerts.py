"""Telegram alerts for interesting aircraft (military, emergency squawks)."""
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from analysis import classify, emergency_reason

# Read secrets from backend/.env (never committed to git)
load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
COOLDOWN_S = 6 * 3600  # don't alert twice for the same aircraft + reason within 6 hours


def enabled():
    """Alerts work only if both secrets are set."""
    return bool(TOKEN and CHAT_ID)


def send_telegram(text):
    """Send a message to our Telegram chat. A failure must never stop the collector."""
    if not enabled():
        return
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        print(f"Telegram error: {error}")


def tags_for(aircraft):
    """The API calls the field 'dbFlags', our database calls it 'db_flags'."""
    return classify({"db_flags": aircraft.get("dbFlags"), "squawk": aircraft.get("squawk")})


def format_alert(aircraft, tag):
    """Build the message text for one aircraft and one reason."""
    icao = aircraft.get("hex")
    flight = (aircraft.get("flight") or "").strip() or "-"
    alt = aircraft.get("alt_baro")
    gs = aircraft.get("gs")

    if tag == "emergency":
        title = f"🚨 Squawk {aircraft.get('squawk')} ({emergency_reason(aircraft)})"
    else:
        title = "🔶 Military aircraft"

    return (
        f"{title} over the Aegean\n"
        f"{flight} ({icao})\n"
        f"Altitude: {alt if alt is not None else '-'} ft · Speed: {round(gs) if gs is not None else '-'} kt\n"
        f"Position: {aircraft['lat']:.3f}, {aircraft['lon']:.3f}\n"
        f"https://globe.adsb.lol/?icao={icao}"
    )


def new_alerts(aircraft_list, sent, now, cooldown_s=COOLDOWN_S):
    """Decide which alerts to send now.

    `sent` remembers when we last alerted for each (icao, reason) and is updated here,
    so the same aircraft does not trigger a message every 15 seconds.
    Returns a list of message texts.
    """
    messages = []
    for aircraft in aircraft_list:
        for tag in tags_for(aircraft):
            key = (aircraft.get("hex"), tag)
            last = sent.get(key)
            if last is not None and now - last < cooldown_s:
                continue
            sent[key] = now
            messages.append(format_alert(aircraft, tag))
    return messages