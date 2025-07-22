#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import requests
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ================== AYARLAR ==================
FROM_DATE = "2025-07-21"
TO_DATE   = "2025-07-22"
INDEX_OID = "4028328c7bf4b5e4017d149764890f47"   # XK100 OID

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAIL_TO   = "ysflkrx@gmail.com"
MAIL_CC   = ""
MAIL_SUBJ = f"Günlük KAP Bildirim Raporu {FROM_DATE} - {TO_DATE}"

MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")

API_URL   = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

payload = {
    "fromDate": FROM_DATE,
    "toDate": TO_DATE,
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

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}
# ============================================

def send_mail(to, cc, subject, html_body):
    if not MAIL_USER or not MAIL_PASS:
        raise RuntimeError("MAIL_USER / MAIL_PASS env değişkenleri yok!")

    msg = MIMEMultipart()
    msg["From"] = MAIL_USER
    msg["To"]   = to
    msg["Cc"]   = cc
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(MAIL_USER, MAIL_PASS)
        s.sendmail(MAIL_USER, [to] + [cc], msg.as_string())

def normalize(records):
    """
    Gönderdiğin örnekteki alanlara göre tablonun kolonlarını oluşturur.
    """
    rows = []
    for r in records:
        link = f"https://www.kap.org.tr/tr/Bildirim/{r.get('disclosureIndex')}" if r.get("disclosureIndex") else ""
        rows.append({
            "Tarih": r.get("publishDate"),
            "Başlık": r.get("kapTitle"),
            "Özet": r.get("summary"),
            "Konu": r.get("subject"),
            "Hisse Kod(lar)ı": r.get("stockCodes"),
            "İlgili Hisseler": r.get("relatedStocks"),
            "Tür": r.get("disclosureClass"),
            "Bildirim No": r.get("disclosureIndex"),
            "Link": link
        })
    return pd.DataFrame(rows)

def main():
    t0 = time.time()

    # 1) API çağrısı
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    print("Status code:", resp.status_code)
    resp.raise_for_status()

    # 2) JSON -> liste
    data = resp.json()
    if isinstance(data, dict):
        # Bazı endpointler dict dönebiliyor, senin örneğin listeydi; yine de esnek olalım
        if "data" in data and isinstance(data["data"], list):
            records = data["data"]
        else:
            records = []
    elif isinstance(data, list):
        records = data
    else:
        records = []

    # 3) DataFrame
    df = normalize(records)

    # Temizlik (satır sonu vs)
    for col in ["Tarih", "Başlık", "Özet", "Konu", "Hisse Kod(lar)ı", "İlgili Hisseler"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r"\\n|\n", " ", regex=True)

    # 4) HTML tablo
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
        <h2>📌 XK100 KAP Bildirimleri ({FROM_DATE} - {TO_DATE})</h2>
        <p>Toplam: {len(df)}</p>
        {html_table}
    </body>
    </html>
    """

    # 5) Mail
    send_mail(MAIL_TO, MAIL_CC, MAIL_SUBJ, html_body)

    print(f"✅ Tamamlandı. Kayıt: {len(df)}, Süre: {(time.time()-t0)/60:.2f} dk")

if __name__ == "__main__":
    main()
