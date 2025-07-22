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
INDEX_OID = "4028328c7bf4b5e4017d149764890f47"  # XK100 için gördüğün oid

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAIL_TO   = "investment@ktportfoy.com.tr"
MAIL_CC   = "bayram.salur@ktportfoy.com.tr"
MAIL_SUBJ = f"Günlük KAP Bildirim Raporu {FROM_DATE} - {TO_DATE}"

# Env değişkenlerinden okunacak
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")

API_URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

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
    msg["To"] = to
    msg["Cc"] = cc
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(MAIL_USER, MAIL_PASS)
        s.sendmail(MAIL_USER, [to] + [cc], msg.as_string())

def normalize(df_json):
    """
    Endpoint'in döndürdüğü JSON yapısını tabloya çevir.
    Aşağıdaki key'ler senin Network'te gördüğün JSON'a göre uyarlanmalı.
    """
    rows = []
    for r in df_json:
        company = r.get("company") or {}
        rows.append({
            "Tarih": r.get("disclosureDate"),
            "Başlık": r.get("title"),
            "Şirket": company.get("companyName"),
            "Kod": company.get("companyCode"),
            "Tür": r.get("disclosureClassName"),
            "Link": f"https://www.kap.org.tr/tr/Bildirim/{r.get('id')}" if r.get("id") else ""
        })
    return pd.DataFrame(rows)

def main():
    t0 = time.time()
    # 1) API çağrısı
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    print("Status code:", resp.status_code)

    resp.raise_for_status()
    data = resp.json()

    # 2) JSON yapısına göre içerik al
    # Tipik varyasyonlar:
    # - {"data": [ {...}, {...} ]}
    # - {"data": {"content": [ ... ]}}
    # - [ {...}, {...} ]
    if isinstance(data, dict):
        if "data" in data:
            if isinstance(data["data"], list):
                content = data["data"]
            elif isinstance(data["data"], dict) and "content" in data["data"]:
                content = data["data"]["content"]
            else:
                content = []
        else:
            # data dict ama 'data' yoksa
            content = data.get("content", [])
    elif isinstance(data, list):
        content = data
    else:
        content = []

    df = normalize(content)

    # Temizlik
    for col in ["Tarih", "Şirket"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r"\\n|\n", " ", regex=True)

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

    # 3) Mail gönder
    send_mail(MAIL_TO, MAIL_CC, MAIL_SUBJ, html_body)

    print(f"✅ Tamamlandı. Kayıt: {len(df)}, Süre: {(time.time()-t0)/60:.2f} dk")

if __name__ == "__main__":
    main()
