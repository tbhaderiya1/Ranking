import ssl
import time
import urllib3
import requests
from bs4 import BeautifulSoup
from flask import Flask, make_response
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LegacyHttpAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = urllib3.util.ssl_.create_urllib3_context()
        ctx.load_default_certs()
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        pool_kwargs['ssl_context'] = ctx
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

app = Flask(__name__)

CACHE_DURATION = 600
cached_html = ""
last_scrape_time = 0

def fetch_and_build():
    global cached_html, last_scrape_time
    current_time = time.time()
    
    if cached_html and (current_time - last_scrape_time < CACHE_DURATION):
        return cached_html

    target_url = "https://services.mpigr.gov.in/svamitva_dashboard/"
    
    try:
        session = requests.Session()
        session.mount('https://', LegacyHttpAdapter())
        res = session.get(target_url, timeout=12)
        
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', id='districtTable')
        
        districts = []
        if table:
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 9:
                        name = cols[1].text.strip()
                        comp_val = cols[8].text.strip().replace(',', '')
                        try:
                            districts.append({"name": name, "completed": int(comp_val)})
                        except ValueError:
                            pass
        
        districts.sort(key=lambda x: x['completed'], reverse=True)
        
        if districts:
            rows_html = "".join([
                f"""
                <div class="row">
                    <div class="rank-name">
                        <span class="rank">{i + 1}</span>
                        <span>{d['name']}</span>
                    </div>
                    <div class="score">{d['completed']:,}</div>
                </div>
                """
                for i, d in enumerate(districts)
            ])
            
            cached_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Svamitva District Ranking</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 16px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
        .header {{ text-align: center; margin-bottom: 20px; position: sticky; top: 0; background: #0f172a; padding: 15px 10px; z-index: 100; width: 100%; border-bottom: 1px solid #334155; }}
        .title {{ font-size: 1.3rem; font-weight: 800; margin: 0; }}
        .subtitle {{ color: #94a3b8; font-size: 0.85rem; margin-top: 4px; }}
        .leaderboard {{ width: 100%; max-width: 480px; display: flex; flex-direction: column; gap: 8px; }}
        .row {{ background: #1e293b; border: 1px solid #334155; padding: 12px 16px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; }}
        .rank-name {{ display: flex; align-items: center; gap: 12px; font-size: 1.05rem; font-weight: 600; }}
        .rank {{ background: #334155; color: #38bdf8; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 0.85rem; font-weight: 700; }}
        .score {{ font-size: 1.25rem; font-weight: 800; color: #38bdf8; background: #0f172a; padding: 4px 10px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 class="title">Svamitva Registration Ranking</h1>
        <div class="subtitle">Ranked by Completed Registries</div>
    </div>
    <div class="leaderboard">
        {rows_html}
    </div>
</body>
</html>"""
            last_scrape_time = current_time
            return cached_html
        else:
            return f"""<!DOCTYPE html>
<html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;padding:30px;text-align:center;">
    <h3>Notice: Table Not Found</h3>
    <p>Connected with status: {res.status_code}, but the data table could not be read.</p>
</body></html>"""

    except Exception as e:
        return f"""<!DOCTYPE html>
<html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;padding:30px;text-align:center;">
    <h3 style="color:#ef4444;">Network Connection Error</h3>
    <p style="color:#cbd5e1;font-size:0.9rem;">{str(e)}</p>
    <p style="font-size:0.85rem;color:#94a3b8;margin-top:20px;">
        If this mentions "ProxyError" or "Connection refused", PythonAnywhere free tier is blocking outbound access to mpigr.gov.in.
    </p>
</body></html>"""

@app.route('/')
def home():
    html_data = fetch_and_build()
    return make_response(html_data)
      
  
