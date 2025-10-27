
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import uvicorn, os, sqlite3, json

app = FastAPI(title='Nest Realtor API')
@app.get("/test")
def test():
    return {"message": "API is working fine"}
# ---- paste below your existing imports and app = FastAPI(...) ----
# required imports for auth/db/lead flow
from fastapi import HTTPException, Depends, Header
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
import jwt
import datetime
import sqlite3
from typing import Optional, List
from pydantic import BaseModel

# config
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_should_replace")
JWT_ALGO = "HS256"
PWD_CTX = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_PATH = "leads.db"  # already used

# ---------- DB helpers ----------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    cur = db.cursor()
    # users, plans, leads
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE,
      password_hash TEXT,
      name TEXT,
      plan TEXT,
      plan_expiry TEXT,
      created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      title TEXT,
      location TEXT,
      phone TEXT,
      potential_commission INTEGER,
      details TEXT,
      status TEXT,
      created_at TEXT,
      FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    db.commit()

# initialize DB at startup
init_db()

# ---------- Models ----------
class SignupModel(BaseModel):
    email: str
    password: str
    name: Optional[str] = ""

class TokenResp(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LeadIn(BaseModel):
    title: str
    location: Optional[str] = ""
    phone: Optional[str] = ""
    potential_commission: Optional[int] = 0
    details: Optional[str] = ""

# ---------- Auth helpers ----------
def hash_password(password: str):
    return PWD_CTX.hash(password)

def verify_password(password: str, hash_: str):
    return PWD_CTX.verify(password, hash_)

def create_jwt(payload: dict, expires_minutes=60*24*7):
    to_encode = payload.copy()
    to_encode.update({"exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGO)

def decode_jwt(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid auth header")
    data = decode_jwt(token)
    user_id = data.get("user_id")
    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(row)

# ---------- Routes ----------

@app.post("/signup")
def signup(payload: SignupModel):
    db = get_db()
    cur = db.cursor()
    pw_hash = hash_password(payload.password)
    now = datetime.datetime.utcnow().isoformat()
    try:
        cur.execute("INSERT INTO users (email,password_hash,name,created_at) VALUES (?,?,?,?)",
                    (payload.email, pw_hash, payload.name, now))
        db.commit()
        uid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")
    token = create_jwt({"user_id": uid})
    return {"access_token": token, "user_id": uid}

@app.post("/login")
def login(form_data: SignupModel):
    # Accept JSON with 'email' and 'password' for simplicity
    db = get_db()
    cur = db.execute("SELECT * FROM users WHERE email = ?", (form_data.email,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if not verify_password(form_data.password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_jwt({"user_id": row["id"]})
    return {"access_token": token}

@app.get("/me")
def me(user = Depends(get_current_user)):
    # user is dict from get_current_user
    return {"user": user}

# Activate plan after payment (call this from frontend after backend verifies Yoco)
@app.post("/activate_plan")
def activate_plan(data: dict, user = Depends(get_current_user)):
    plan = data.get("plan")
    months = int(data.get("months", 1))
    if not plan:
        raise HTTPException(status_code=400, detail="Missing plan")
    db = get_db()
    now = datetime.datetime.utcnow()
    expiry = now + datetime.timedelta(days=30*months)
    db.execute("UPDATE users SET plan = ?, plan_expiry = ? WHERE id = ?", (plan, expiry.isoformat(), user["id"]))
    db.commit()
    return {"status": "activated", "plan": plan, "expires": expiry.isoformat()}

# Create lead (used by bot or admin)
@app.post("/leads/create")
def create_lead(payload: LeadIn, user = Depends(get_current_user)):
    db = get_db()
    now = datetime.datetime.utcnow().isoformat()
    cur = db.cursor()
    cur.execute("""
      INSERT INTO leads (user_id,title,location,phone,potential_commission,details,status,created_at)
      VALUES (?,?,?,?,?,?,?,?)""",
      (user["id"], payload.title, payload.location, payload.phone, payload.potential_commission, payload.details, "new", now))
    db.commit()
    return {"status":"ok", "lead_id": cur.lastrowid}

# List leads for current user
@app.get("/leads")
def list_leads(user = Depends(get_current_user)):
    db = get_db()
    cur = db.execute("SELECT * FROM leads WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))
    rows = [dict(r) for r in cur.fetchall()]
    return {"leads": rows}

# Simple bot endpoint to generate dummy leads (placeholder for AI)
@app.post("/generate_leads")
def generate_leads(count: int = 3, user = Depends(get_current_user)):
    db = get_db()
    cur = db.cursor()
    now = datetime.datetime.utcnow().isoformat()
    created = []
    for i in range(count):
        title = f"Seller lead {i+1} - {user['id']}"
        location = "Cape Town"
        phone = f"07100000{str(i+1).zfill(2)}"
        potential = 45000 + i*5000
        details = "Auto-generated lead (test)"
        cur.execute("""INSERT INTO leads (user_id,title,location,phone,potential_commission,details,status,created_at)
                       VALUES (?,?,?,?,?,?,?,?)""", (user["id"], title, location, phone, potential, details, "new", now))
        created.append(cur.lastrowid)
    db.commit()
    return {"created": len(created)}

# A simple route to allow frontend to POST payment token and then activate plan
@app.post("/complete_payment")
def complete_payment(data: dict):
    # data expected: { token, amount, plan, user_email (optional) }
    # This endpoint will verify with Yoco using your secret key, then activate plan for the user (if logged in)
    token = data.get("token")
    amount = data.get("amount")
    plan = data.get("plan")
    user_email = data.get("user_email")
    secret = os.getenv("YOCO_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="Missing YOCO_SECRET_KEY")
    # verify with Yoco
    resp = requests.post("https://online.yoco.com/v1/charges/", headers={"X-Auth-Secret-Key": secret}, json={
        "token": token,
        "amountInCents": amount,
        "currency": "ZAR"
    })
    j = resp.json()
    if resp.status_code == 200 and j.get("status") == "successful":
        # find user by email (if provided) and activate
        if user_email:
            db = get_db()
            cur = db.execute("SELECT * FROM users WHERE email = ?", (user_email,))
            row = cur.fetchone()
            if row:
                # activate plan for 1 month
                expiry = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
                db.execute("UPDATE users SET plan = ?, plan_expiry = ? WHERE id = ?", (plan, expiry, row["id"]))
                db.commit()
        return {"status": "success", "yoco": j}
    else:
        raise HTTPException(status_code=400, detail={"yoco": j})

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
@app.post("/verify_payment")
async def verify_payment(request: Request):
    data = await request.json()
    payment_id = data.get("payment_id")

    if not payment_id:
        return {"status": "error", "message": "Missing payment_id"}

    secret_key = os.getenv("YOCO_SECRET_KEY")
    if not secret_key:
        return {"status": "error", "message": "Missing Yoco secret key"}

    headers = {
        "X-Auth-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }

    # Yoco API endpoint for verifying a charge
    url = f"https://online.yoco.com/v1/charges/{payment_id}"

    try:
        response = requests.get(url, headers=headers)
        yoco_response = response.json()

        if response.status_code == 200 and yoco_response.get("status") == "successful":
            return {"status": "success", "message": "Payment verified successfully", "details": yoco_response}
        else:
            return {"status": "failed", "message": "Payment verification failed", "details": yoco_response}

    except Exception as e:
        return {"status": "error", "message": str(e)}


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
