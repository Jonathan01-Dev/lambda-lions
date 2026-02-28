import socket
import struct
import asyncio
import logging
from src.cli.ui import info
from src.protocol.packet import Packet
from src.protocol.types import HELLO

logger = logging.getLogger(__name__)

MCAST_GRP = '239.255.42.99'
MCAST_PORT = 6000

class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, discovery):
        self.discovery = discovery
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.discovery._handle_packet(data, addr)

    def error_received(self, exc):
        logger.error(f"UDP Error received: {exc}")

class MulticastDiscovery:
    def __init__(self, node_id, tcp_port, peer_table):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.peer_table = peer_table
        self.running = False
        self._send_task = None
        self.transport = None
        self.protocol = None

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # On Windows, we bind to '' (0.0.0.0)
        sock.bind(('', MCAST_PORT))
        
        # Join multicast group on all interfaces
        mreq = struct.pack("4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton("0.0.0.0"))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # TTL and Loopback (Crucial for same-PC testing)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        return sock

    async def start(self):
        self.running = True
        loop = asyncio.get_running_loop()
        
        try:
            sock = self._create_socket()
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: DiscoveryProtocol(self),
                sock=sock
            )
            self._send_task = asyncio.create_task(self._send_loop())
            logger.info(f"Discovery service started on {MCAST_GRP}:{MCAST_PORT}")
            # info(f"Discovery active on port {MCAST_PORT}") # Less spam in UI
        except Exception as e:
            logger.error(f"Failed to start discovery service: {e}")
            info(f"[Error] Discovery failed: {e}")

    async def stop(self):
        self.running = False
        if self._send_task:
            self._send_task.cancel()
        if self.transport:
            self.transport.close()
        logger.info("Discovery service stopped")

    async def _send_loop(self):
        # Separate socket for sending to avoid binding issues
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        
        payload = struct.pack("!H", self.tcp_port)
        packet = Packet(HELLO, self.node_id, payload)
        data = packet.serialize()

        while self.running:
            try:
                send_sock.sendto(data, (MCAST_GRP, MCAST_PORT))
                # Periodic log to show we are still alive
                # logger.debug(f"Broadcasted HELLO for port {self.tcp_port}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error sending discovery packet: {e}")
                await asyncio.sleep(2)

    def _handle_packet(self, data, addr):
        try:
            # logger.debug(f"Received UDP packet from {addr}, len={len(data)}")
            packet = Packet.deserialize(data)
            if packet.type == HELLO:
                # Filter out ourselves
                if packet.node_id == self.node_id:
                    return 
                
                peer_port = struct.unpack("!H", packet.payload)[0]
                peer_host = addr[0]
                
                # Use a specific log format for S1 demo
                info(f"[[bold green]Discovery[/bold green]] New Peer: [cyan]{packet.node_id.hex()[:8]}[/cyan] at [magenta]{peer_host}:{peer_port}[/magenta]")
                
                self.peer_table.add_peer(
                    packet.node_id.hex(),
                    peer_host,
                    peer_port,
                    asyncio.get_event_loop().time()
                )
                
                # Notify node of discovery
                if hasattr(self.peer_table, 'node') and self.peer_table.node:
                    asyncio.create_task(self.peer_table.node.on_peer_discovered(packet.node_id.hex()))
        except Exception as e:
            # logger.debug(f"Received non-Archipel or malformed packet from {addr}: {e}")
            pass
