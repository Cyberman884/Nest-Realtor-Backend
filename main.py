from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
import sqlite3, os, jwt, datetime

# Import the bots
from bots import generate_combined_leads

# -------------------- APP CONFIG --------------------
app = FastAPI(title="Nest Realtor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev/testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_should_replace")
JWT_ALGO = "HS256"
PWD_CTX = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_PATH = "leads.db"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# -------------------- DATABASE --------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password_hash TEXT,
        plan TEXT DEFAULT 'starter',
        created_at TEXT
    )
    """)
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
    )
    """)
    db.commit()


init_db()


# -------------------- MODELS --------------------
class SignupModel(BaseModel):
    name: Optional[str] = ""
    email: str
    password: str


class LoginModel(BaseModel):
    email: str
    password: str


# -------------------- AUTH HELPERS --------------------
def hash_password(password: str):
    return PWD_CTX.hash(password)


def verify_password(password: str, hash_: str):
    return PWD_CTX.verify(password, hash_)


def create_jwt(payload: dict, expires_minutes=60 * 24 * 7):
    to_encode = payload.copy()
    to_encode.update({"exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGO)


def decode_jwt(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(token: str = Depends(oauth2_scheme)):
    data = decode_jwt(token)
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (data["user_id"],))
    user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)


# -------------------- ROUTES --------------------
@app.get("/")
def home():
    return {"message": "Nest Realtor API is running 🚀"}


@app.post("/signup")
def signup(user: SignupModel):
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO users (name, email, password_hash, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (user.name, user.email, hash_password(user.password)))
        db.commit()
        return {"message": "Signup successful"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")


@app.post("/login")
def login(user: LoginModel):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (user.email,))
    row = cur.fetchone()
    if not row or not verify_password(user.password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token = create_jwt({"user_id": row["id"], "email": row["email"]})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/automate")
def automate(current_user: dict = Depends(get_current_user)):
    """
    Automatically generate leads based on user's plan.
    """
    plan = current_user.get("plan", "starter")
    leads = generate_combined_leads(plan)

    db = get_db()
    cur = db.cursor()
    created_count = 0

    for lead in leads:
        cur.execute("""
            INSERT INTO leads (user_id, title, location, phone, potential_commission, details, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            current_user["id"],
            lead["title"],
            lead["location"],
            lead["phone"],
            lead["potential_commission"],
            lead.get("source", ""),
            lead["status"]
        ))
        created_count += 1

    db.commit()
    return {"message": "Leads generated successfully", "created": created_count}


@app.get("/leads")
def get_leads(current_user: dict = Depends(get_current_user)):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM leads WHERE user_id=? ORDER BY created_at DESC", (current_user["id"],))
    leads = [dict(row) for row in cur.fetchall()]
    return {"leads": leads}


# -------------------- RUN --------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
