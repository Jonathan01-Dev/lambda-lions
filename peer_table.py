"""Peer routing table using SQLite."""

import sqlite3


class PeerTable:
    def __init__(self, db_file='peer_table.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS peers (
            node_id TEXT PRIMARY KEY,
            host TEXT,
            port INTEGER,
            last_seen REAL
            )"""
        )

    def add_peer(self, node_id, host, port, last_seen):
        self.conn.execute(
            "INSERT OR REPLACE INTO peers VALUES (?, ?, ?, ?)",
            (node_id, host, port, last_seen)
        )
        self.conn.commit()

    def get_peer(self, node_id):
        cursor = self.conn.execute(
            "SELECT host, port FROM peers WHERE node_id = ?",
            (node_id,)
        )
        return cursor.fetchone()

    def list_peers(self):
        cursor = self.conn.execute("SELECT node_id, host, port FROM peers")
        return cursor.fetchall()
