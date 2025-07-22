#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, date

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    ZoneInfo = None

# ================== AYARLAR ==================
INDEX_OID = "4028328c7bf4b5e4017d149764890f47"  # XK100 OID
API_URL   = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAIL_TO   = "ysflkrx@gmail.com"
MAIL_CC   = ""

MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")

# ================================================================

def tr_today() -> date:
    """Türkiye saatine göre bugünün tarihi."""
    if ZoneInfo:
        return datetime.now(ZoneInfo("Europe/Istanbul")).date()
    return (datetime.utcnow() + timedelta(hours=3)).date()  # fallback

def calc_date_range() -> tuple[str, str]:
    """
    Kural:
      - Pazartesi ise: fromDate = bugün - 3 gün (Cuma), toDate = bugün
      - Diğer günler: fromDate = bugün - 1 gün (dün), toDate = bugün
    """
    today = tr_today()
    if today.weekday() == 0:  # Pazartesi
        from_d = today - timedelta(days=3)
    else:
        from_d = today - timedelta(days=1)
    return from_d.isoformat(), today.isoformat()

def build_payload(from_date: str, to_date: str) -> dict:
    return {
        "fromDate": from_date,
        "toDate": to_date,
        "memberType": "IGS",
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "disclosureClass": "",
        "subjectList": [],
        "isLate": "",
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "marketOid": "",
        "index": INDEX_OID,
        "bdkReview": "",
        "bdkMemberOidList": [],
        "year": "",
        "term": "",
        "ruleType": "",
        "period": "",
        "fromSrc": False,
        "srcCategory": "",
        "disclosureIndexList": []
    }

def fetch_disclosures(payload: dict) -> list:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return data["data"]
    return []

def normalize(records: list) -> pd.DataFrame:
    """
    İstenen kolon dizilimi:
    # | Tarih | Kod | Şirket | Konu | Özet Bilgi | İlgili Şirketler
    """
    rows = []
    for r in records:
        rows.append({
            "Tarih": r.get("publishDate"),
            "Kod": r.get("stockCodes"),
            "Şirket": r.get("kapTitle"),
            "Konu": r.get("subject"),
            "Özet Bilgi": r.get("summary"),
            "İlgili Şirketler": r.get("relatedStocks")
        })
    df = pd.DataFrame(rows)
    df.insert(0, "#", range(1, len(df) + 1))

    # Temizlik
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(r"\\n|\n", " ", regex=True)
    return df

def send_mail(to: str, cc: str, subject: str, html_body: str):
    if not MAIL_USER or not MAIL_PASS:
        raise RuntimeError("MAIL_USER / MAIL_PASS bulunamadı. GitHub Secrets'ta tanımla.")

    msg = MIMEMultipart()
    msg["From"] = MAIL_USER
    msg["To"]   = to
    msg["Cc"]   = cc
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(MAIL_USER, MAIL_PASS)
        s.sendmail(MAIL_USER, [to] + [cc], msg.as_string())

def main():
    t0 = time.time()

    from_date, to_date = calc_date_range()
    print(f"FROM_DATE: {from_date}, TO_DATE: {to_date}")

    payload = build_payload(from_date, to_date)
    records = fetch_disclosures(payload)
    df = normalize(records)

    html_table = df.to_html(index=False, border=1, justify="center")
    html_body = f"""
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            table {{ border-collapse: collapse; font-family: Arial; font-size: 12px; }}
            th, td {{ border: 1px solid #ddd; padding: 6px; text-align: center; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h2>📌 XK100 KAP Bildirimleri ({from_date} - {to_date})</h2>
        <p>Toplam: {len(df)}</p>
        {html_table}
    </body>
    </html>
    """

    send_mail(MAIL_TO, MAIL_CC, f"Günlük KAP Bildirim Raporu {from_date} - {to_date}", html_body)
    print(f"✅ Tamamlandı. Kayıt: {len(df)}, Süre: {(time.time() - t0)/60:.2f} dk")

if __name__ == "__main__":
    main()
