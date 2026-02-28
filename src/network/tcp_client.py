import asyncio
import struct
import logging
from src.protocol.constants import MAGIC
from src.crypto.pki import get_encryption_keys, get_public_encryption_key
from src.crypto.handshake import Handshake
from src.crypto.session import Session

logger = logging.getLogger(__name__)


NETWORK_TIMEOUT = 10.0

class TCPClient:
    def __init__(self, node, host, port=7777):
        self.node = node
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.session = None

    async def connect(self):
        """Connect and perform Archipel handshake."""
        logger.info(f"Connecting to {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=NETWORK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout to {self.host}:{self.port}")
            raise ConnectionError(f"Connection timeout to {self.host}:{self.port}")
        
        try:
            # --- Handshake Phase ---
            # 1. Send our Ed25519 PublicKey + Port
            self.writer.write(struct.pack("!IBH", MAGIC, 0x01, self.node.tcp_port) + self.node.vk.encode())
            await asyncio.wait_for(self.writer.drain(), timeout=NETWORK_TIMEOUT)
            
            # 2. Wait for Responder's Header (7 bytes: MAGIC + TYPE + PORT)
            header = await asyncio.wait_for(self.reader.readexactly(7), timeout=NETWORK_TIMEOUT)
            magic, pkt_type, remote_port = struct.unpack("!IBH", header)
            
            if magic != MAGIC or pkt_type != 0x01:
                raise ValueError("Invalid handshake response from peer")
                
            remote_ed_pk_bytes = await asyncio.wait_for(self.reader.readexactly(32), timeout=NETWORK_TIMEOUT)
            
            # 3. Derive Session Key
            from nacl.signing import VerifyKey
            remote_vk = VerifyKey(remote_ed_pk_bytes)
            remote_x_pk = get_public_encryption_key(remote_vk)
            
            local_x_sk, _ = get_encryption_keys(self.node.sk)
            
            handshake = Handshake(local_x_sk)
            session_key = handshake.derive_session_key(remote_x_pk)
            self.session = Session(session_key)
            
            peer_id = remote_ed_pk_bytes.hex()
            self.node.sessions[peer_id] = self.session
            
            # Record peer in table
            self.node.peer_table.add_peer(
                peer_id, 
                self.host, 
                self.port, 
                asyncio.get_event_loop().time()
            )
            
            logger.info(f"Secure session established with {peer_id[:16]}... at {self.host}:{self.port}")
            return peer_id
            
        except ConnectionRefusedError:
            logger.error(f"Connection refused to {self.host}:{self.port}. Is the other node running?")
            raise
        except Exception as e:
            logger.error(f"Handshake failed with {self.host}:{self.port}: {e}", exc_info=True)
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            raise

    async def send_encrypted(self, data: bytes):
        """Encrypt and send data."""
        if self.session is None:
            await self.connect()
            
        encrypted = self.session.encrypt(data)
        # Prefix with length
        self.writer.write(struct.pack("!I", len(encrypted)) + encrypted)
        await self.writer.drain()

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
