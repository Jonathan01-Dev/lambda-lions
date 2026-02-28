"""Packet types and constants."""

# Packet type codes
HELLO = 0x01
PEER_LIST = 0x02
MSG = 0x03
CHUNK_REQ = 0x04
CHUNK_DATA = 0x05
MANIFEST = 0x06
ACK = 0x07
PING = 0x08
PONG = 0x09

PACKET_TYPES = {
    HELLO: "HELLO",
    PEER_LIST: "PEER_LIST",
    MSG: "MSG",
    CHUNK_REQ: "CHUNK_REQ",
    CHUNK_DATA: "CHUNK_DATA",
    MANIFEST: "MANIFEST",
    ACK: "ACK",
    PING: "PING",
    PONG: "PONG",
}
