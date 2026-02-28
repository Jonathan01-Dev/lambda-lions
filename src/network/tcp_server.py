import asyncio
import struct
import logging
from src.protocol.constants import MAGIC
from src.crypto.pki import get_encryption_keys, get_public_encryption_key
from src.crypto.handshake import Handshake
from src.crypto.session import Session
from src.cli.ui import info, success

logger = logging.getLogger(__name__)


class TCPServer:
    def __init__(self, node, host='0.0.0.0', port=7777):
        self.node = node
        self.host = host
        self.port = port
        self.server = None

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        logger.info(f"Incoming connection from {addr}")
        
        try:
            # --- Handshake Phase ---
            # 1. Wait for Initiator's Ed25519 PublicKey
            header = await reader.readexactly(5) # MAGIC + 0x01
            magic, pkt_type = struct.unpack("!IB", header)
            
            if magic != MAGIC or pkt_type != 0x01:
                logger.warning(f"Invalid handshake from {addr}")
                writer.close()
                return

            remote_ed_pk_bytes = await reader.readexactly(32)
            
            # 2. Send our Ed25519 PublicKey
            writer.write(struct.pack("!IB", MAGIC, 0x01) + self.node.vk.encode())
            await writer.drain()
            
            # 3. Derive Session Key
            from nacl.signing import VerifyKey
            remote_vk = VerifyKey(remote_ed_pk_bytes)
            remote_x_pk = get_public_encryption_key(remote_vk)
            
            local_x_sk, _ = get_encryption_keys(self.node.sk)
            
            handshake = Handshake(local_x_sk)
            session_key = handshake.derive_session_key(remote_x_pk)
            session = Session(session_key)
            
            peer_id = remote_ed_pk_bytes.hex()
            self.node.sessions[peer_id] = session
            
            success(f"Secure session established with remote node {peer_id[:16]}... at {addr}")
            logger.info(f"Handshake complete. Local node ID: {self.node.vk.encode().hex()[:16]}... Remote node ID: {peer_id[:16]}...")
            
            # --- Encrypted Communication Phase ---
            while True:
                # Read encrypted packet length (4 bytes)
                len_data = await reader.read(4)
                if not len_data:
                    logger.info(f"Connection closed by peer {addr}")
                    break
                
                pkt_len = struct.unpack("!I", len_data)[0]
                encrypted_pkt = await reader.readexactly(pkt_len)
                
                # Decrypt and pass to node
                decrypted = session.decrypt(encrypted_pkt)
                logger.debug(f"Decrypted message from {peer_id[:8]}: {len(decrypted)} bytes")
                self.node.on_message_received(peer_id, decrypted)
                
        except Exception as e:
            logger.error(f"Error in TCP session with {addr}: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        bind_addr = self.server.sockets[0].getsockname()
        info(f"TCP server listening on {self.host}:{self.port} (Bound to {bind_addr})")
        logger.info(f"Server started. Accepting connections on {bind_addr}")
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
