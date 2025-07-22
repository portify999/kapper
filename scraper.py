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
    from zoneinfo import ZoneInfo  # Py 3.9+
except ImportError:
    ZoneInfo = None

###############################################################################
# AYARLAR
###############################################################################
INDEX_OID = "4028328c7bf4b5e4017d149764890f47"   # XK100
API_URL   = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAIL_TO = "investment@ktportfoy.com.tr,yusuf.ulker@ktportfoy.com.tr"
MAIL_CC = "bayram.salur@ktportfoy.com.tr"

MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")

# ---------------------------------------------------------------------------
# 2025 & 2026 TÜRKİYE RESMÎ TATİLLERİ  (yarım günler de tam tatil sayıldı)
# Kaynak: timeanddate.com, officeholidays.com, publicholidays.me
# ---------------------------------------------------------------------------
HOLIDAYS = {
    # 2025
    date(2025, 1, 1),   # Yılbaşı
    date(2025, 3, 29),  # Ramazan Bayramı Arife (yarım) - tam sayıyoruz
    date(2025, 3, 30),  # Ramazan Bayramı 1
    date(2025, 3, 31),  # Ramazan Bayramı 2
    date(2025, 4, 1),   # Ramazan Bayramı 3
    date(2025, 4, 23),  # 23 Nisan
    date(2025, 5, 1),   # 1 Mayıs
    date(2025, 5, 19),  # 19 Mayıs
    date(2025, 6, 5),   # Kurban Bayramı Arife (yarım)
    date(2025, 6, 6),   # Kurban 1
    date(2025, 6, 7),   # Kurban 2
    date(2025, 6, 8),   # Kurban 3
    date(2025, 6, 9),   # Kurban 4
    date(2025, 7, 15),  # 15 Temmuz
    date(2025, 8, 30),  # 30 Ağustos
    date(2025, 10, 28), # 29 Ekim arife (yarım)
    date(2025, 10, 29), # 29 Ekim

    # 2026
    date(2026, 1, 1),   # Yılbaşı
    date(2026, 3, 19),  # Ramazan Bayramı Arife (tahmini yarım)
    date(2026, 3, 20),  # Ramazan Bayramı 1
    date(2026, 3, 21),  # Ramazan Bayramı 2
    date(2026, 3, 22),  # Ramazan Bayramı 3
    date(2026, 4, 23),  # 23 Nisan
    date(2026, 5, 1),   # 1 Mayıs
    date(2026, 5, 19),  # 19 Mayıs
    date(2026, 5, 26),  # Kurban Bayramı Arife (yarım) - tahmini
    date(2026, 5, 27),  # Kurban 1
    date(2026, 5, 28),  # Kurban 2
    date(2026, 5, 29),  # Kurban 3
    date(2026, 5, 30),  # Kurban 4
    date(2026, 7, 15),  # 15 Temmuz
    date(2026, 8, 30),  # 30 Ağustos
    date(2026, 10, 28), # 29 Ekim arife (yarım)
    date(2026, 10, 29), # 29 Ekim
}
###############################################################################


def tr_today() -> date:
    """Türkiye saatine göre bugünün tarihi."""
    if ZoneInfo:
        return datetime.now(ZoneInfo("Europe/Istanbul")).date()
    return (datetime.utcnow() + timedelta(hours=3)).date()  # fallback


def is_non_business(d: date) -> bool:
    """Hafta sonu veya resmi tatil mi?"""
    return d.weekday() >= 5 or d in HOLIDAYS


def calc_date_range() -> tuple[str, str]:
    """
    - toDate = bugünün tarihi (eğer iş günü değilse, en yakın önceki iş günü)
    - fromDate = toDate'den önceki ardışık iş dışı gün sayısı + 1 kadar geriye git
      (Pazartesi veya tatil sonrası mantığı)
    """
    to_d = tr_today()
    # Eğer bugün de iş dışıysa, en yakın iş gününe geri sar
    while is_non_business(to_d):
        to_d -= timedelta(days=1)

    # Dünden başlayıp geriye doğru iş dışı günleri say
    count_off = 0
    probe = to_d - timedelta(days=1)
    while is_non_business(probe):
        count_off += 1
        probe -= timedelta(days=1)

    from_d = to_d - timedelta(days=count_off + 1)
    return from_d.isoformat(), to_d.isoformat()


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
    Kolonlar: # | Tarih | Kod | Şirket | Konu | Özet Bilgi | İlgili Şirketler
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


def send_mail(to, cc="", subject="", html_body=""):
    to_list = [e.strip() for e in to.split(",")]                # "a@x.com,b@y.com"
    cc_list = [e.strip() for e in cc.split(",")] if cc else []  # boş olabilir

    msg = MIMEMultipart()
    msg["From"] = "Yusuf Ülker"
    msg["To"]   = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = to_list + cc_list

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(MAIL_USER, MAIL_PASS)
        s.sendmail(MAIL_USER, recipients, msg.as_string())



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
        <h2>📌 XK100 KAP Bildirimleri </h2>
        <p>Toplam: {len(df)}</p>
        {html_table}
    </body>
    </html>
    """

    send_mail(MAIL_TO, MAIL_CC,
              f"Günlük KAP Bildirim Raporu ({from_date} & {to_date})",
              html_body)

    print(f"✅ Tamamlandı. Kayıt: {len(df)}, Süre: {(time.time()-t0)/60:.2f} dk")


if __name__ == "__main__":
    main()
