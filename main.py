import sqlite3
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Customer Support CRM")

# CORS setup for Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serve index.html as homepage
@app.get("/")
def read_root():
    return FileResponse("index.html")


# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            customer_name TEXT,
            customer_email TEXT,
            subject TEXT,
            description TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT,
            updated_at TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            note_text TEXT,
            created_at TEXT
        )
    """
    )
    conn.commit()
    conn.close()


init_db()


# --- MODELS ---
class TicketCreate(BaseModel):
    customer_name: str
    customer_email: str
    subject: str
    description: str


class TicketUpdate(BaseModel):
    status: str
    note: Optional[str] = None


# --- API ENDPOINTS ---
@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0] + 1001
    ticket_id = f"TKT-{count}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO tickets (ticket_id, customer_name, customer_email, subject, description, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'Open', ?, ?)
    """,
        (
            ticket_id,
            ticket.customer_name,
            ticket.customer_email,
            ticket.subject,
            ticket.description,
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()
    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": "Ticket created successfully",
    }


@app.get("/api/tickets")
def get_tickets(status: Optional[str] = None, search: Optional[str] = None):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()

    query = "SELECT ticket_id, customer_name, customer_email, subject, status, created_at FROM tickets WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (customer_name LIKE ? OR ticket_id LIKE ? OR customer_email LIKE ? OR subject LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term, search_term])

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    tickets = []
    for r in rows:
        tickets.append(
            {
                "ticket_id": r[0],
                "customer_name": r[1],
                "customer_email": r[2],
                "subject": r[3],
                "status": r[4],
                "created_at": r[5],
            }
        )
    return tickets


@app.get("/api/tickets/{ticket_id}")
def get_ticket_detail(ticket_id: str):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT ticket_id, customer_name, customer_email, subject, description, status, created_at FROM tickets WHERE ticket_id = ?",
        (ticket_id,),
    )
    t = cursor.fetchone()

    if not t:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    cursor.execute(
        "SELECT note_text, created_at FROM notes WHERE ticket_id = ? ORDER BY id DESC",
        (ticket_id,),
    )
    notes = cursor.fetchall()
    conn.close()

    return {
        "ticket_id": t[0],
        "customer_name": t[1],
        "customer_email": t[2],
        "subject": t[3],
        "description": t[4],
        "status": t[5],
        "created_at": t[6],
        "notes": [{"note_text": n[0], "created_at": n[1]} for n in notes],
    }


@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, data: TicketUpdate):
    conn = sqlite3.connect("tickets.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
        (data.status, now, ticket_id),
    )

    if data.note:
        cursor.execute(
            "INSERT INTO notes (ticket_id, note_text, created_at) VALUES (?, ?, ?)",
            (ticket_id, data.note, now),
        )

    conn.commit()
    conn.close()
    return {"success": True, "updated_at": now}
from mangum import Mangum

handler = Mangum(app)