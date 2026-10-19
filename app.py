import time
import requests
import ssl
import urllib3
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from flask import Flask

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LegacyHttpAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = urllib3.util.ssl_.create_urllib3_context()
        ctx.load_default_certs()
        ctx.options |= 0x4  # Allow legacy server connect
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        pool_kwargs['ssl_context'] = ctx
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

app = Flask(__name__)

CACHE_DURATION = 600  # 10 minutes
cached_html = ""
last_scrape_time = 0

def get_leaderboard_html():
    global cached_html, last_scrape_time
    current_time = time.time()
    
    if cached_html and (current_time - last_scrape_time < CACHE_DURATION):
        return cached_html

    try:
        session = requests.Session()
        session.mount('https://', LegacyHttpAdapter())
        TARGET_URL = "https://services.mpigr.gov.in/svamitva_dashboard/"
        res = session.get(TARGET_URL, timeout=15)
        res.raise_for_status() # This will surface an error message instead of a blank page if blocked
        
        soup = BeautifulSoup(res.text, 'html.parser')
        districts = []
        
        table = soup.find('table', id='districtTable')
        if table:
            tbody = table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 9:
                        name = cols[1].text.strip()
                        completed_str = cols[8].text.strip().replace(',', '')
                        try:
                            districts.append({"name": name, "completed": int(completed_str)})
                        except ValueError:
                            pass
        
        # Sort by highest completed registries
        districts.sort(key=lambda x: x['completed'], reverse=True)
        
        if districts:
            rows_html = ""
            for index, dist in enumerate(districts):
                rows_html += f"""
                <div class="row">
                    <div class="rank-name">
                        <span class="rank">{index + 1}</span>
                        <span>{dist['name']}</span>
                    </div>
                    <div class="score">{dist['completed']:,}</div>
                </div>
                """
                
            cached_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Svamitva District Ranking</title>
                <style>
                    body {{ background: #0f172a; color: #f8fafc; font-family: -apple-system, sans-serif; margin: 0; padding: 16px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
                    .header {{ text-align: center; margin-bottom: 20px; position: sticky; top: 0; background: #0f172a; padding: 15px 10px; z-index: 100; width: 100%; border-bottom: 1px solid #334155; }}
                    .title {{ font-size: 1.4rem; font-weight: 800; margin: 0; color: #f8fafc; }}
                    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-top: 6px; }}
                    .leaderboard {{ width: 100%; max-width: 500px; display: flex; flex-direction: column; gap: 8px; }}
                    .row {{ background: #1e293b; border: 1px solid #334155; padding: 12px 16px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; }}
                    .rank-name {{ display: flex; align-items: center; gap: 12px; font-size: 1.1rem; font-weight: 600; }}
                    .rank {{ background: #334155; color: #38bdf8; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 0.95rem; font-weight: bold; }}
                    .score {{ font-size: 1.3rem; font-weight: 800; color: #38bdf8; background: #0f172a; padding: 4px 12px; border-radius: 8px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1 class="title">Svamitva Registration</h1>
                    <div class="subtitle">Ranked by Completed Registries</div>
                </div>
                <div class="leaderboard">
                    {rows_html}
                </div>
            </body>
            </html>
            """
            last_scrape_time = current_time
        else:
            return "<h2 style='color:white; text-align:center;'>Could not locate the data table on the target website.</h2>"
            
    except Exception as e:
        return f"<h2 style='color:white; text-align:center; padding: 20px;'>Error fetching data: {e}</h2>"
        
    return cached_html

@app.route('/')
def home():
    return get_leaderboard_html()
    
