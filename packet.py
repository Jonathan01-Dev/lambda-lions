"""Archipel packet builder and parser."""

import struct
from .types import PACKET_TYPES
from .constants import MAGIC, HEADER_SIZE, SIGNATURE_SIZE


class Packet:
    def __init__(self, pkt_type, node_id, payload):
        self.type = pkt_type
        self.node_id = node_id
        self.payload = payload

    def serialize(self) -> bytes:
        """Serialize packet to bytes with MAGIC, type, node_id, payload_len."""
        payload_len = len(self.payload)
        header = struct.pack(
            '!IBB32sI',
            MAGIC,
            1,  # version
            self.type,
            self.node_id,
            payload_len
        )
        return header + self.payload

    @staticmethod
    def deserialize(data: bytes):
        """Deserialize bytes to Packet."""
        if len(data) < HEADER_SIZE:
            raise ValueError("Packet too short")
        magic, version, pkt_type, node_id, payload_len = struct.unpack(
            '!IBB32sI',
            data[:HEADER_SIZE]
        )
        if magic != MAGIC:
            raise ValueError("Invalid magic")
        payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
        return Packet(pkt_type, node_id, payload)
