import asyncio
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil

from src.core.node import Node
from src.protocol.packet import Packet
from src.protocol import types

from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("archipel-api")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app = FastAPI(title="Archipel High-Fidelity API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Node instance
node = None
messages = [] # chat
system_logs = [] # protocol logs
MAX_MESSAGES = 100

def log_system(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    system_logs.append({"content": msg, "time": time_str})
    if len(system_logs) > 50: system_logs.pop(0)

class ConnectRequest(BaseModel):
    host: str
    port: int = 7777

class SendMessageRequest(BaseModel):
    peer_id: str
    content: str

@app.on_event("startup")
async def startup_event():
    global node
    port = int(os.getenv("ARCHIPEL_PORT", 7777))
    node = Node(f"web-node-{port}", tcp_port=port)
    log_system(f"Archipel Node initialized on port {port}")
    
    # Patch node to capture messages
    original_on_message = node.on_message_received
    def patched_on_message(sender_id, data):
        try:
            packet = Packet.deserialize(data)
            if packet.type == types.MSG:
                content = packet.payload.decode(errors='replace')
                time_str = datetime.now().strftime("%H:%M")
                messages.append({"sender": sender_id, "content": content, "time": time_str})
                log_system(f"Message received from {sender_id[:8]}")
        except Exception as e:
            log_system(f"Raw data received from {sender_id[:8]}")
        
        if len(messages) > MAX_MESSAGES:
            messages.pop(0)
        original_on_message(sender_id, data)
    
    node.on_message_received = patched_on_message
    
    try:
        await node.start()
        logger.info(f"Archipel Node started on P2P port {node.tcp_port}")
    except OSError:
        logger.warning(f"Port {port} busy, trying {port+1}...")
        node.tcp_port = port + 1
        await node.start()
        logger.info(f"Archipel Node started on fallback P2P port {node.tcp_port}")

@app.get("/api/logs")
async def get_logs():
    return system_logs

@app.get("/api/status")
async def get_status():
    return {
        "node_id": node.node_id.hex() if node else None,
        "port": node.tcp_port if node else None,
        "peers_count": len(node.peer_table.list_peers()) if node else 0,
        "uptime": "Active"
    }

@app.get("/api/peers")
async def get_peers():
    peers = node.peer_table.list_peers()
    return [{"id": p[0], "host": p[1], "port": p[2], "short_id": p[0][:8]} for p in peers]

@app.get("/api/transfers")
async def get_transfers():
    # Return active downloads and uploads
    downloads = getattr(node, "_active_downloads", {})
    uploads = getattr(node, "_active_uploads", {})
    
    res = {"downloads": [], "uploads": []}
    for k, v in downloads.items():
        recv = len(v.get("received", {}))
        total = len(v.get("chunk_hashes", []))
        progress = (recv / total * 100) if total > 0 else 0
        res["downloads"].append({"file": v["filename"], "progress": round(progress, 1), "status": "receiving"})
        
    for k, v in uploads.items():
        res["uploads"].append({"file": v["filename"], "status": "seeding"})
        
    return res

@app.post("/api/connect")
async def connect_peer(req: ConnectRequest):
    log_system(f"Connecting to {req.host}:{req.port}...")
    try:
        from src.network.tcp_client import TCPClient
        client = TCPClient(node, req.host, req.port)
        peer_id = await client.connect()
        await client.close()
        log_system(f"Handshake successful with {peer_id[:8]}")
        return {"status": "success", "peer_id": peer_id}
    except Exception as e:
        log_system(f"Connection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send")
async def send_message(req: SendMessageRequest):
    log_system(f"Sending message to {req.peer_id[:8]}")
    try:
        packet = Packet(types.MSG, node.node_id, req.content.encode())
        await node.send_to_peer(req.peer_id, packet.serialize())
        time_str = datetime.now().strftime("%H:%M")
        messages.append({"sender": "me", "content": req.content, "time": time_str})
        if len(messages) > MAX_MESSAGES:
            messages.pop(0)
        return {"status": "sent"}
    except Exception as e:
        log_system(f"Send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages")
async def get_messages():
    return messages

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log_system(f"File uploaded to node: {file.filename}")
        return {"filename": file.filename, "local_path": os.path.abspath(file_path)}
    except Exception as e:
        log_system(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-file")
async def send_file(req: SendMessageRequest):
    # Reuse SendMessageRequest, content is the local_path
    log_system(f"Starting P2P transfer of {os.path.basename(req.content)} to {req.peer_id[:8]}")
    try:
        # Node's send_file is async
        asyncio.create_task(node.send_file(req.peer_id, req.content))
        return {"status": "transfer_started"}
    except Exception as e:
        log_system(f"P2P Send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask-ai")
async def ask_ai(req: SendMessageRequest):
    log_system("Querying Gemini AI Assistant...")
    try:
        from src.messaging.gemini import GeminiIntegration
        gemini = GeminiIntegration()
        response = gemini.query(req.content)
        time_str = datetime.now().strftime("%H:%M")
        messages.append({"sender": "AI", "content": response, "time": time_str})
        log_system("Gemini AI responded.")
        return {"response": response}
    except Exception as e:
        log_system(f"AI Assistant Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serve the static UI
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
