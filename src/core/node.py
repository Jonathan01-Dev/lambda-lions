from src.network.tcp_server import TCPServer
from src.network.tcp_client import TCPClient
import logging

logger = logging.getLogger(__name__)

class Node:
    def __init__(self, node_name="node1", tcp_port=7777, bootstrap_peer=None):
        self.name = node_name
        self.tcp_port = tcp_port
        self.bootstrap_peer = bootstrap_peer
        
        # Unique DB for each instance to avoid locking
        from src.network.peer_table import PeerTable
        db_path = f"peer_table_{tcp_port}.db"
        self.peer_table = PeerTable(db_path, node=self)
        
        from src.crypto.pki import generate_keypair
        self.sk, self.vk = generate_keypair()
        self.node_id = self.vk.encode()
        
        from src.network.multicast import MulticastDiscovery
        self.discovery = MulticastDiscovery(self.node_id, self.tcp_port, self.peer_table)
        self.tcp_server = TCPServer(self, port=self.tcp_port)
        self.sessions = {} # peer_id_hex -> Session object
        self._sent_greetings = set() # To avoid greeting multiple times in same session

    async def start(self):
        """Start the node (multicast listener, TCP server, etc.)."""
        import asyncio
        # Start TCP server in background
        self._server_task = asyncio.create_task(self.tcp_server.start())
        # Start discovery
        await self.discovery.start()
        
        # Connect to bootstrap peer if provided
        if self.bootstrap_peer:
            logger.info(f"Attempting to connect to bootstrap peer: {self.bootstrap_peer}")
            try:
                host, port = self.bootstrap_peer.split(":")
                client = TCPClient(self, host, int(port))
                # Sending a greeting to establish a session
                greeting = f"Bootstrap greeting from {self.name}!".encode()
                await client.send_encrypted(greeting)
                await client.close()
                logger.info(f"Bootstrap connection to {self.bootstrap_peer} successful.")
            except Exception as e:
                logger.error(f"Failed to connect to bootstrap peer {self.bootstrap_peer}: {e}")

    async def on_peer_discovered(self, peer_id_hex: str):
        """Called when a new peer is found via Multicast UDP."""
        if peer_id_hex in self._sent_greetings:
            return
            
        self._sent_greetings.add(peer_id_hex)
        logger.info(f"Automatically connecting to new peer: {peer_id_hex[:8]}...")
        
        # Send a secure greeting
        try:
            greeting = f"Secure Hello from {self.name}!".encode()
            await self.send_to_peer(peer_id_hex, greeting)
        except Exception as e:
            logger.error(f"Failed auto-greeting to {peer_id_hex[:8]}: {e}")
            # Remove from set so we can retry later if needed
            self._sent_greetings.discard(peer_id_hex)

    async def stop(self):
        """Stop the node gracefully."""
        await self.discovery.stop()
        await self.tcp_server.stop()
        self._server_task.cancel()

    def on_message_received(self, sender_id: str, data: bytes):
        """Callback for TCPServer when a decrypted message is received."""
        from src.protocol.packet import Packet
        from src.protocol import types
        
        try:
            packet = Packet.deserialize(data)
            
            if packet.type == types.MSG:
                logger.info(f"Received message from {sender_id[:8]}: {packet.payload.decode(errors='replace')}")
                
            elif packet.type == types.MANIFEST:
                # Payload: Filename\0TotalSize\0Hash\0ChunkHash1,ChunkHash2...
                parts = packet.payload.split(b"\0")
                if len(parts) >= 4:
                    filename = parts[0].decode(errors="replace")
                    total_size = int(parts[1])
                    file_hash = parts[2].hex()
                    chunk_hashes = [h.hex() for h in parts[3].split(b",")]
                    
                    logger.info(f"Received MANIFEST for {filename} ({total_size} bytes)")
                    # Store in active downloads (simplified)
                    if not hasattr(self, "_active_downloads"):
                        self._active_downloads = {}
                    
                    self._active_downloads[file_hash] = {
                        "filename": filename,
                        "total_size": total_size,
                        "chunk_hashes": chunk_hashes,
                        "received": {},
                        "sender_id": sender_id
                    }
                    
                    # Start requesting chunks
                    import asyncio
                    asyncio.create_task(self._request_next_chunk(sender_id, file_hash))
                    
            elif packet.type == types.CHUNK_REQ:
                # Payload: FileHash(32b) + ChunkHash(32b)
                if len(packet.payload) == 64:
                    file_hash = packet.payload[:32].hex()
                    chunk_hash = packet.payload[32:].hex()
                    asyncio.create_task(self._send_chunk(sender_id, file_hash, chunk_hash))

            elif packet.type == types.PING:
                from src.protocol.packet import Packet
                pong = Packet(types.PONG, self.node_id, b"PONG")
                asyncio.create_task(self.send_to_peer(sender_id, pong.serialize()))
                logger.debug(f"Received PING from {sender_id[:8]}, sent PONG")

            elif packet.type == types.PONG:
                logger.info(f"Received PONG from {sender_id[:8]}")
                if hasattr(self, "on_pong"):
                    self.on_pong(sender_id)

            elif packet.type == types.CHUNK_DATA:
                # Payload: FileHash(32b) + ChunkHash(32b) + Data
                if len(packet.payload) > 64:
                    file_hash = packet.payload[:32].hex()
                    chunk_hash = packet.payload[32:].hex()
                    chunk_data = packet.payload[64:]
                    
                    if hasattr(self, "_active_downloads") and file_hash in self._active_downloads:
                        dl = self._active_downloads[file_hash]
                        dl["received"][chunk_hash] = chunk_data
                        logger.info(f"Received chunk {chunk_hash[:8]} for {dl['filename']}")
                        
                        # Request next or finalize
                        import asyncio
                        asyncio.create_task(self._request_next_chunk(sender_id, file_hash))
            
            else:
                # Fallback for legacy raw messages
                logger.debug(f"Received non-packet data or unknown type: {packet.type}")
                
        except Exception:
            # Handle legacy raw strings (pre-Packet implementation)
            if data.startswith(b"/file "):
                header_end = data.find(b" ", 6)
                if header_end != -1:
                    filename = data[6:header_end].decode(errors='replace')
                    file_content = data[header_end+1:]
                    import os
                    os.makedirs("downloads", exist_ok=True)
                    safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")
                    filepath = os.path.join("downloads", f"received_{safe_name}")
                    with open(filepath, "wb") as f:
                        f.write(file_content)
                    logger.info(f"Received legacy file '{filename}' from {sender_id[:8]} saved to {filepath}")
                    return
            logger.info(f"Received raw message from {sender_id[:8]}: {data.decode(errors='replace')}")

    async def _request_next_chunk(self, peer_id, file_hash):
        if file_hash not in self._active_downloads:
            return
            
        dl = self._active_downloads[file_hash]
        for ch in dl["chunk_hashes"]:
            if ch not in dl["received"]:
                # Request this chunk
                from src.protocol.packet import Packet
                from src.protocol import types
                payload = bytes.fromhex(file_hash) + bytes.fromhex(ch)
                packet = Packet(types.CHUNK_REQ, self.node_id, payload)
                await self.send_to_peer(peer_id, packet.serialize())
                return
        
        # All chunks received!
        await self._finalize_download(file_hash)

    async def _finalize_download(self, file_hash):
        dl = self._active_downloads.pop(file_hash)
        import os
        os.makedirs("downloads", exist_ok=True)
        safe_name = "".join(c for c in dl["filename"] if c.isalnum() or c in "._-")
        filepath = os.path.join("downloads", safe_name)
        
        with open(filepath, "wb") as f:
            for ch in dl["chunk_hashes"]:
                f.write(dl["received"][ch])
        
        logger.info(f"TRANSACTION COMPLETE: File {dl['filename']} saved to {filepath}")

    async def send_file(self, peer_id_hex: str, filepath: str):
        """Split file into chunks, send manifest, and wait for CHUNK_REQ."""
        import os
        import hashlib
        from src.protocol.packet import Packet
        from src.protocol import types
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File {filepath} not found")
            
        filename = os.path.basename(filepath)
        total_size = os.path.getsize(filepath)
        
        # Split into chunks (512KB each)
        chunk_size = 512 * 1024
        chunks = []
        chunk_hashes = []
        file_hash_obj = hashlib.sha256()
        
        with open(filepath, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                chunks.append(data)
                ch = hashlib.sha256(data).digest()
                chunk_hashes.append(ch)
                file_hash_obj.update(data)
        
        file_hash = file_hash_obj.digest()
        
        # Store for CHUNK_REQ responses (Active Uploads)
        if not hasattr(self, "_active_uploads"):
            self._active_uploads = {}
        
        file_hash_hex = file_hash.hex()
        self._active_uploads[file_hash_hex] = {
            "filename": filename,
            "chunks": {ch.hex(): data for ch, data in zip(chunk_hashes, chunks)}
        }
        
        # Construct and send MANIFEST
        # Format: Filename\0TotalSize\0Hash(raw)\0ChunkHash1,ChunkHash2...
        payload = filename.encode() + b"\0" + str(total_size).encode() + b"\0" + file_hash + b"\0" + b",".join(chunk_hashes)
        manifest_packet = Packet(types.MANIFEST, self.node_id, payload)
        
        logger.info(f"STARTING TRANSFER: {filename} ({total_size} bytes, {len(chunks)} chunks)")
        await self.send_to_peer(peer_id_hex, manifest_packet.serialize())
        logger.info(f"Sent MANIFEST for {filename} to {peer_id_hex[:8]}")

    async def _send_chunk(self, peer_id, file_hash, chunk_hash):
        """Handle CHUNK_REQ from peer."""
        if hasattr(self, "_active_uploads") and file_hash in self._active_uploads:
            up = self._active_uploads[file_hash]
            if chunk_hash in up["chunks"]:
                chunk_data = up["chunks"][chunk_hash]
                from src.protocol.packet import Packet
                from src.protocol import types
                
                # Payload: FileHash(32b) + ChunkHash(32b) + Data
                payload = bytes.fromhex(file_hash) + bytes.fromhex(chunk_hash) + chunk_data
                packet = Packet(types.CHUNK_DATA, self.node_id, payload)
                await self.send_to_peer(peer_id, packet.serialize())
                logger.info(f"CHUNK SENT: {chunk_hash[:8]} of file {file_hash[:8]} to {peer_id[:8]}")
            else:
                logger.warning(f"Requested chunk {chunk_hash[:8]} not found in active upload")
        else:
            logger.warning(f"Requested file hash {file_hash[:8]} not found in active uploads")

    async def send_to_peer(self, peer_id_hex: str, data: bytes):
        """Find peer in table, connect, and send encrypted data."""
        peer_info = self.peer_table.get_peer(peer_id_hex)
        if not peer_info:
            err = f"Peer {peer_id_hex[:8]} not found in table."
            logger.error(err)
            raise ValueError(err)

        host, port = peer_info
        from src.network.tcp_client import TCPClient
        client = TCPClient(self, host, port)
        try:
            # Note: data might already be a serialized Packet or a raw string
            # In either case, the TCPClient will encrypt it and send it
            await client.send_encrypted(data)
            await client.close()
        except Exception as e:
            logger.error(f"Failed to send to {peer_id_hex[:8]} at {host}:{port}: {e}")
            raise
