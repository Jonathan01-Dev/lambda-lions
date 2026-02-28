import asyncio
import struct
import logging
from src.protocol.constants import MAGIC
from src.crypto.pki import get_encryption_keys, get_public_encryption_key
from src.crypto.handshake import Handshake
from src.crypto.session import Session

logger = logging.getLogger(__name__)


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
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        
        try:
            # --- Handshake Phase ---
            # 1. Send our Ed25519 PublicKey
            self.writer.write(struct.pack("!IB", MAGIC, 0x01) + self.node.vk.encode())
            await self.writer.drain()
            
            # 2. Wait for Responder's Ed25519 PublicKey
            header = await self.reader.readexactly(5)
            magic, pkt_type = struct.unpack("!IB", header)
            
            if magic != MAGIC or pkt_type != 0x01:
                raise ValueError("Invalid handshake response from peer")
                
            remote_ed_pk_bytes = await self.reader.readexactly(32)
            
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
            
            logger.info(f"Secure session established with {peer_id[:16]}... at {self.host}:{self.port}")
            
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
