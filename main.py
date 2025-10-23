
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import uvicorn, os, sqlite3, json

app = FastAPI(title='Nest Realtor API')
@app.get("/test")
def test_route():
    return {"status": "success", "message": "Nest Realtor backend is fully live!"}
import requests

@app.get("/test_payment")
def test_payment():
    secret_key = os.getenv("YOCO_SECRET_KEY")
    if not secret_key:
        return {"error": "Missing Yoco secret key in environment variables"}

    headers = {
        "X-Auth-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }

    # Simulated test payment payload
    payload = {
        "token": "tok_test_visa_4242_03",
        "amountInCents": 1000,  # R10.00
        "currency": "ZAR"
    }

    response = requests.post(
        "https://online.yoco.com/v1/charges/",
        headers=headers,
        json=payload
    )

    return {
        "status": response.status_code,
        "response": response.json()
    }


DB = 'leads.db'

def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('CREATE TABLE leads (id INTEGER PRIMARY KEY, title TEXT, location TEXT, price TEXT, source TEXT, url TEXT)')
        sample = [
            ('3 Bedroom House','Pretoria','R1,500,000','Demo','https://example.com/1'),
            ('Luxury Apartment','Cape Town','R2,300,000','Demo','https://example.com/2'),
            ('Vacant Land','Johannesburg','R750,000','Demo','https://example.com/3'),
            ('Townhouse','Durban','R1,200,000','Demo','https://example.com/4')
        ]
        c.executemany('INSERT INTO leads (title,location,price,source,url) VALUES (?,?,?,?,?)', sample)
        conn.commit()
        conn.close()

@app.on_event('startup')
def startup():
    init_db()

@app.get('/api/search')
def api_search(q: str = None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if q:
        c.execute("SELECT id,title,location,price,source,url FROM leads WHERE title LIKE ? OR location LIKE ?", (f'%{q}%',f'%{q}%'))
    else:
        c.execute("SELECT id,title,location,price,source,url FROM leads")
    rows = c.fetchall()
    leads = []
    for r in rows:
        leads.append({'id':r[0],'title':r[1],'location':r[2],'price':r[3],'source':r[4],'url':r[5]})
    conn.close()
    return {'leads':leads}

@app.get('/api/health')
def health():
    return {'status':'ok'}

@app.get('/')
def root():
    return {'message':'Nest Realtor API'}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
