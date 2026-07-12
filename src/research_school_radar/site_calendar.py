from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote, urlencode

from .site_paths import slug


def google_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    params = {
        "action": "TEMPLATE",
        "text": summary,
        "dates": f"{start}/{end}",
        "details": description,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def outlook_calendar_url(deadline: date, title: str, url: str) -> str:
    summary, description = _calendar_event(deadline, title, url)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": summary,
        "startdt": deadline.isoformat(),
        "enddt": (deadline + timedelta(days=1)).isoformat(),
        "allday": "true",
        "body": description,
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params)


def calendar_data_url(deadline: date, title: str, url: str) -> str:
    start = deadline.strftime("%Y%m%d")
    end = (deadline + timedelta(days=1)).strftime("%Y%m%d")
    stamp = date.today().strftime("%Y%m%d")
    uid = f"{start}-{slug(title)}@research-seasonal-school-radar"
    summary = _ics_text(f"Application deadline: {title}")
    description = _ics_text(
        f"Apply by {deadline.isoformat()}. Source: {url}" if url else f"Apply by {deadline.isoformat()}."
    )
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Summa//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}T000000Z",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return "data:text/calendar;charset=utf-8," + quote(ics)


def calendar_filename(title: str) -> str:
    return f"{slug(title) or 'deadline'}-deadline.ics"


def _calendar_event(deadline: date, title: str, url: str) -> tuple[str, str]:
    summary = f"Application deadline: {title}"
    description = f"Apply by {deadline.isoformat()}." + (f" Source: {url}" if url else "")
    return summary, description


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
