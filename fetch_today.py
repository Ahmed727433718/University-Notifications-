"""Daily study brief: reads a Moodle iCal link, builds a small page, sends a phone notification.

Secrets/env (never commit these):
  CALENDAR_URL  - the Moodle "export calendar" URL (required)
  NTFY_TOPIC    - topic name for ntfy push notifications (optional)
Optional env: TZ_NAME (default Asia/Jerusalem), NOTIFY_HOUR (default 7),
              PAGE_URL (link opened when tapping the notification), FORCE_NOTIFY=1
"""
import html
import json
import os
import sys
from datetime import datetime, timedelta, date, time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Jerusalem"))
NOTIFY_HOUR = int(os.environ.get("NOTIFY_HOUR", "7"))
DAYS_AHEAD = 7
DAY_CODES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

QUIZ_WORDS = ("quiz", "exam", "test", "كويز", "اختبار", "امتحان")
DUE_WORDS = ("due", "assign", "deadline", "closes", "تسليم", "واجب", "مهمة", "يغلق")


def icon_for(title: str) -> str:
    t = title.lower()
    if any(w in t for w in QUIZ_WORDS):
        return "📝"
    if any(w in t for w in DUE_WORDS):
        return "📌"
    return "📅"


def unescape(text: str) -> str:
    return (text.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\").strip())


def parse_dt(params: dict, value: str):
    """Parse an iCal DTSTART value. Returns (aware datetime in TZ, all_day flag)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or len(value) == 8:
        d = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(d, time.min, tzinfo=TZ), True
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(TZ), False
    dt = datetime.strptime(value, "%Y%m%dT%H%M%S")
    try:
        src = ZoneInfo(params["TZID"]) if "TZID" in params else TZ
    except Exception:  # unknown TZID name: assume local time
        src = TZ
    return dt.replace(tzinfo=src).astimezone(TZ), False


def parse_ics(text: str):
    """Minimal iCalendar reader for Moodle exports (VEVENT with DTSTART/SUMMARY/CATEGORIES).
    Recurring rules (RRULE) are not expanded: Moodle exports each event separately."""
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]  # unfold continuation line
        else:
            lines.append(raw)

    events, cur = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            if cur is not None and "dtstart" in cur:
                start, all_day = cur["dtstart"]
                events.append({"start": start, "all_day": all_day,
                               "title": cur.get("title", ""), "course": cur.get("course", "")})
            cur = None
        elif cur is not None and ":" in ln:
            head, _, value = ln.partition(":")
            name, *plist = head.split(";")
            params = dict(p.split("=", 1) for p in plist if "=" in p)
            name = name.upper()
            if name == "DTSTART":
                try:
                    cur["dtstart"] = parse_dt(params, value)
                except ValueError:
                    pass
            elif name == "SUMMARY":
                cur["title"] = unescape(value)
            elif name == "CATEGORIES":
                cur["course"] = unescape(value)
    return events


def load_calendar_events(url: str):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return parse_ics(resp.text)


def load_lectures(today: date):
    """Weekly lectures from schedule.json (optional): [{"day":"sun","time":"08:00","title":"...","room":"..."}]"""
    path = Path(__file__).with_name("schedule.json")
    if not path.exists():
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"schedule.json is not valid JSON: {exc}", file=sys.stderr)
        return []
    events = []
    for offset in range(DAYS_AHEAD + 1):
        d = today + timedelta(days=offset)
        for item in items:
            if item.get("day", "").lower()[:3] == DAY_CODES[d.weekday()]:
                hh, mm = map(int, item["time"].split(":"))
                events.append({
                    "start": datetime.combine(d, time(hh, mm), tzinfo=TZ),
                    "all_day": False,
                    "title": "محاضرة: " + item.get("title", ""),
                    "course": item.get("room", ""),
                })
    return events


def fmt_time(ev):
    return "طوال اليوم" if ev["all_day"] else ev["start"].strftime("%H:%M")


def line(ev):
    extra = f" ({ev['course']})" if ev["course"] else ""
    return f"{icon_for(ev['title'])} {fmt_time(ev)} — {ev['title']}{extra}"


def build_html(days, now):
    parts = []
    for d, evs in days:
        label = "اليوم" if d == now.date() else ("بكرة" if d == now.date() + timedelta(days=1) else DAY_AR[d.weekday()])
        parts.append(f"<section><h2>{label} <small>{d.strftime('%d/%m')}</small></h2>")
        if not evs:
            parts.append('<p class="empty">ما في شي 🎉</p>')
        for ev in evs:
            course = f"<span class='course'>{html.escape(ev['course'])}</span>" if ev["course"] else ""
            parts.append(
                f"<div class='ev'><span class='t'>{fmt_time(ev)}</span>"
                f"<span class='n'>{icon_for(ev['title'])} {html.escape(ev['title'])}{course}</span></div>"
            )
        parts.append("</section>")
    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>شو عندي اليوم</title>
<style>
:root{{--bg:#f6f7fb;--card:#fff;--tx:#1b1f2a;--mu:#6b7280;--ac:#5b3cc4}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12141a;--card:#1c1f28;--tx:#eceef4;--mu:#9aa1b2;--ac:#a58bff}}}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif}}
main{{max-width:560px;margin:0 auto;padding:16px}}
h1{{font-size:1.3rem;margin:8px 0 16px}}
section{{background:var(--card);border-radius:14px;padding:12px 14px;margin-bottom:12px}}
h2{{font-size:1.05rem;margin:0 0 8px;color:var(--ac)}} h2 small{{color:var(--mu);font-weight:400}}
.ev{{display:flex;gap:10px;padding:8px 0;border-top:1px solid rgba(128,128,128,.18)}}
.ev:first-of-type{{border-top:0}}
.t{{min-width:4.2rem;color:var(--mu);font-variant-numeric:tabular-nums}}
.n{{flex:1}} .course{{display:block;color:var(--mu);font-size:.85rem}}
.empty{{color:var(--mu);margin:4px 0}} footer{{color:var(--mu);font-size:.8rem;text-align:center;margin:16px 0}}
</style></head><body><main>
<h1>📚 شو عندي اليوم</h1>
{''.join(parts)}
<footer>آخر تحديث: {now.strftime('%d/%m %H:%M')}</footer>
</main></body></html>"""


def notify(topic: str, body: str, click: str):
    payload = {"topic": topic, "title": "📚 شو عندك اليوم", "message": body}
    if click:
        payload["click"] = click
    r = requests.post("https://ntfy.sh/", json=payload, timeout=30)
    r.raise_for_status()


def main():
    url = os.environ.get("CALENDAR_URL", "").strip()
    if not url:
        sys.exit("CALENDAR_URL is not set")

    now = datetime.now(TZ)
    today = now.date()
    events = load_calendar_events(url) + load_lectures(today)

    days = []
    for offset in range(DAYS_AHEAD + 1):
        d = today + timedelta(days=offset)
        evs = sorted((e for e in events if e["start"].date() == d), key=lambda e: e["start"])
        days.append((d, evs))

    out = Path("site")
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(build_html(days, now), encoding="utf-8")

    today_evs = days[0][1]
    tomorrow_n = len(days[1][1])
    body = "\n".join(line(e) for e in today_evs) if today_evs else "ما في شي اليوم 🎉"
    if tomorrow_n:
        body += f"\n\nبكرة: {tomorrow_n} موعد"
    print(body)

    topic = os.environ.get("NTFY_TOPIC", "").strip()
    due_now = now.hour == NOTIFY_HOUR or os.environ.get("FORCE_NOTIFY") == "1"
    if topic and due_now:
        notify(topic, body, os.environ.get("PAGE_URL", "").lower())
        print("notification sent")
    else:
        print("notification skipped")


if __name__ == "__main__":
    main()
