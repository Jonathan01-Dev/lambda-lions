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

    def _get_all_ips(self):
        """Get all local IPv4 addresses to join multicast on each interface."""
        ips = []
        try:
            # On Windows, we can use socket's getaddrinfo for better enumeration
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except Exception as e:
            logger.warning(f"Failed to enumerate local IPs: {e}")
        return ips

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to all interfaces
        sock.bind(('', MCAST_PORT))
        
        # Join multicast group on all detected interfaces
        # This is vital for Wi-Fi Direct / Ad-hoc interfaces
        ips = self._get_all_ips()
        for ip in ips:
            try:
                mreq = struct.pack("4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton(ip))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                logger.info(f"Multicast membership added on interface: {ip}")
            except Exception as e:
                logger.debug(f"Could not add multicast on interface {ip}: {e}")
        
        # Always join on 0.0.0.0 as fallback
        try:
            mreq = struct.pack("4s4s", socket.inet_aton(MCAST_GRP), socket.inet_aton("0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except: pass

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
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
            logger.info(f"Aggressive Discovery started on {MCAST_GRP}:{MCAST_PORT}")
        except Exception as e:
            logger.error(f"Failed to start discovery service: {e}")

    async def stop(self):
        self.running = False
        if self._send_task:
            self._send_task.cancel()
        if self.transport:
            self.transport.close()
        logger.info("Discovery service stopped")

    async def _send_loop(self):
        # Socket for sending
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) # Enable broadcast
        send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        
        payload = struct.pack("!H", self.tcp_port)
        packet = Packet(HELLO, self.node_id, payload)
        data = packet.serialize()

        while self.running:
            try:
                # 1. Send Multicast
                send_sock.sendto(data, (MCAST_GRP, MCAST_PORT))
                
                # 2. Send Subnet Broadcast (Aggressive Fallback)
                # We send to 255.255.255.255 to reach everyone on local segments
                send_sock.sendto(data, ('<broadcast>', MCAST_PORT))
                
                # Faster interval for hackathon discovery
                await asyncio.sleep(4)
            except Exception as e:
                logger.error(f"Error in discovery send: {e}")
                await asyncio.sleep(4)

    def _handle_packet(self, data, addr):
        try:
            packet = Packet.deserialize(data)
            if packet.type == HELLO:
                if packet.node_id == self.node_id:
                    return 
                
                peer_port = struct.unpack("!H", packet.payload)[0]
                peer_host = addr[0]
                
                # Register in table
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
