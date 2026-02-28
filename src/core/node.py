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
        logger.info(f"Received message from {sender_id[:8]}: {data.decode(errors='replace')}")

    async def send_to_peer(self, peer_id_hex: str, data: bytes):
        """Find peer in table, connect, and send encrypted data."""
        peer_info = self.peer_table.get_peer(peer_id_hex)
        if not peer_info:
            logger.error(f"Peer {peer_id_hex[:8]} not found in table.")
            return

        host, port = peer_info
        client = TCPClient(self, host, port)
        try:
            await client.send_encrypted(data)
            await client.close()
        except Exception as e:
            logger.error(f"Failed to send to {peer_id_hex[:8]}: {e}")
