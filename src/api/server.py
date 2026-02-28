import asyncio
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os

from src.core.node import Node
from src.protocol.packet import Packet
from src.protocol import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("archipel-api")

app = FastAPI(title="Archipel P2P API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Node instance
node = None
messages = [] # Global message log for the UI

class Message(BaseModel):
    sender: str
    content: str
    timestamp: str

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
    
    # Patch node to capture messages
    original_on_message = node.on_message_received
    def patched_on_message(sender_id, data):
        try:
            packet = Packet.deserialize(data)
            if packet.type == types.MSG:
                content = packet.payload.decode(errors='replace')
                messages.append({"sender": sender_id, "content": content})
        except:
            messages.append({"sender": sender_id, "content": data.decode(errors='replace')})
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

@app.get("/api/status")
async def get_status():
    return {
        "node_id": node.node_id.hex() if node else None,
        "port": node.tcp_port if node else None,
        "peers_count": len(node.peer_table.list_peers()) if node else 0
    }

@app.get("/api/peers")
async def get_peers():
    peers = node.peer_table.list_peers()
    return [{"id": p[0], "host": p[1], "port": p[2]} for p in peers]

@app.post("/api/connect")
async def connect_peer(req: ConnectRequest):
    try:
        from src.network.tcp_client import TCPClient
        client = TCPClient(node, req.host, req.port)
        peer_id = await client.connect()
        await client.close()
        return {"status": "success", "peer_id": peer_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send")
async def send_message(req: SendMessageRequest):
    try:
        packet = Packet(types.MSG, node.node_id, req.content.encode())
        await node.send_to_peer(req.peer_id, packet.serialize())
        messages.append({"sender": "me", "content": req.content})
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages")
async def get_messages():
    return messages

@app.post("/api/ask-ai")
async def ask_ai(req: SendMessageRequest):
    try:
        from src.messaging.gemini import GeminiIntegration
        gemini = GeminiIntegration()
        response = gemini.query(req.content)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve the static UI
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
