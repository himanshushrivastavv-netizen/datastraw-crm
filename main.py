from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import sqlite3
from typing import Optional
from datetime import datetime

app = FastAPI()

# Database Setup
def get_db_connection():
    conn = sqlite3.connect("crm.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            note_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Models
class TicketCreate(BaseModel):
    customer_name: str
    customer_email: str
    subject: str
    description: str

class TicketUpdate(BaseModel):
    status: str
    note: Optional[str] = None

# API Endpoints
@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    count = cursor.fetchone()[0] + 1001
    ticket_id = f"TKT-{count}"
    
    cursor.execute(
        "INSERT INTO tickets (ticket_id, customer_name, customer_email, subject, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        (ticket_id, ticket.customer_name, ticket.customer_email, ticket.subject, ticket.description, "Open")
    )
    conn.commit()
    conn.close()
    return {"ticket_id": ticket_id, "status": "Open", "message": "Ticket created successfully"}

@app.get("/api/tickets")
def get_tickets(status: Optional[str] = None, search: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (customer_name LIKE ? OR customer_email LIKE ? OR ticket_id LIKE ? OR subject LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tickets

@app.get("/api/tickets/{ticket_id}")
def get_ticket_detail(ticket_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    cursor.execute("SELECT * FROM notes WHERE ticket_id = ? ORDER BY created_at DESC", (ticket_id,))
    notes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    result = dict(ticket)
    result["notes"] = notes
    return result

@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update_data: TicketUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
        (update_data.status, ticket_id)
    )
    
    if update_data.note and update_data.note.strip():
        cursor.execute(
            "INSERT INTO notes (ticket_id, note_text) VALUES (?, ?)",
            (ticket_id, update_data.note.strip())
        )
        
    conn.commit()
    conn.close()
    return {"success": True, "message": "Ticket updated successfully"}

# DELETE Endpoint
@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
    cursor.execute("DELETE FROM notes WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Ticket deleted successfully"}

# Serve Frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")
