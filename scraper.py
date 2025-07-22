from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import datetime
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

start_time = time.perf_counter()
start_date = "21.07.2025"
end_date = "22.07.2025"

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)
results = []

def wait_and_click(xpath):
    try:
        elem = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        try:
            elem.click()
        except:
            driver.execute_script("arguments[0].click();", elem)
    except Exception as e:
        print(f"❌ Tıklama hatası: {xpath}\n{e}")

def extract_table(result_list):
    try:
        table = wait.until(EC.presence_of_element_located((By.ID, 'financialTable')))
        rows = table.find_elements(By.TAG_NAME, "tr")
        if len(rows) >= 2:
            headers = [th.text.strip() for th in rows[0].find_elements(By.TAG_NAME, "th")]
            for row in rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                record = {headers[i]: cells[i].text.strip() for i in range(len(headers))}
                result_list.append(record)
            print("✅ kayıt alındı.")
    except Exception as e:
        print(f"❌ tablo hatası: {e}")

def write_date_input(input_elem, date_string):
    driver = input_elem._parent
    wait = WebDriverWait(driver, 10)
    gun, ay, yil = map(int, date_string.split('.'))
    hedef_ts = int(datetime.datetime(yil, ay, gun).timestamp()) * 1000

    input_elem.click()
    time.sleep(0.2)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label[contains(.,'calendar view is open')]]"))).click()
    time.sleep(0.2)
    wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space(text())='{yil}']"))).click()
    time.sleep(0.2)
    wait.until(EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space(text())='{_ay_index_ters(ay)}']"))).click()
    time.sleep(0.2)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"button[data-timestamp='{hedef_ts}']:not(:disabled)"))).click()
    time.sleep(0.2)

def _ay_index_ters(ay):
    return {
        1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
        7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"
    }[ay]

def send_mail(to, cc, subject, html_body):
    msg = MIMEMultipart()
    msg['From'] = os.getenv("MAIL_USER")
    msg['To'] = to
    msg['Cc'] = cc
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.getenv("MAIL_USER"), os.getenv("MAIL_PASS"))
        server.sendmail(msg['From'], [to] + [cc], msg.as_string())

# Siteye git
driver.get("https://www.kap.org.tr/tr/bildirim-sorgu")
driver.execute_script("window.scrollBy(0, 500);")
time.sleep(0.5)

Date2_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id=":r2:"]')))
Date1_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id=":r0:"]')))

write_date_input(Date1_input, start_date)
wait_and_click("//button[contains(@class, 'MuiPickersDay-root') and contains(@class, 'Mui-selected') and @aria-selected='true']")
write_date_input(Date2_input, end_date)
wait_and_click("//button[contains(@class, 'MuiPickersDay-root') and contains(@class, 'Mui-selected') and @aria-selected='true']")

wait_and_click("//div[contains(text(), 'Detaylı Sorgulama')]")
wait_and_click('//*[@id="panel1a-content"]/div/div/div[1]/div[3]/div/div[1]')
wait_and_click('//*[@id="panel1a-content"]/div/div/div[1]/div[3]/div/div[2]/div/div[62]')
wait_and_click('//*[@id="detailed-inquiry-content"]/div[1]/div/div/form/div[2]/button[2]')

time.sleep(2)
extract_table(results)
time.sleep(1)

driver.quit()
df = pd.DataFrame(results)

if "Tarih" in df.columns:
    df["Tarih"] = df["Tarih"].str.replace('\n', ' ', regex=True)
if "İlgili Şirketler" in df.columns:
    df["İlgili Şirketler"] = df["İlgili Şirketler"].str.replace('\n', ', ', regex=True)
    df["İlgili Şirketler"] = df["İlgili Şirketler"].str.replace('\n', ', ', regex=True)

remove_cols = ["Tip", "Yıl", "Periyot", "İşlemler"]
if not df.empty:
    for col in remove_cols:
        if col in df.columns:
            df.drop(col, axis=1, inplace=True)
    print(f"💾 {start_date}-{end_date} aralığındaki kayıtlar: {len(df)}")
else:
    print("📭 Kayıtlar boş.")

html_today = df.to_html(index=False, border=1, justify="center")

html_body = f"""
<html>
<head>
    <style>
        table {{ border-collapse: collapse; font-family: Arial; font-size: 12px; }}
        th, td {{ border: 1px solid #ddd; padding: 6px; text-align: center; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h2>📌 XK100 KAP Bildirimleri</h2>
    {html_today}
</body>
</html>
"""

send_mail(
    "investment@ktportfoy.com.tr",
    "bayram.salur@ktportfoy.com.tr",
    f"Günlük KAP Bildirim Raporu {start_date} - {end_date}",
    html_body
)

elapsed = (time.perf_counter() - start_time) / 60
print(f"⏱️ Toplam çalışma süresi: {elapsed:.2f} dakika")
