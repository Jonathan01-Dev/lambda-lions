#!/usr/bin/env python3
"""Main entry point for Archipel P2P Network."""

import argparse
import sys
import asyncio
from src.core.node import Node
from src.cli.ui import info, success
from src.core.logger import setup_logging


async def main():
    """Initialize and run the node."""
    logger = setup_logging()
    
    parser = argparse.ArgumentParser(description="Archipel P2P Node")
    parser.add_argument("--port", type=int, default=7777, help="TCP port to listen on")
    parser.add_argument("--peer", type=str, help="Bootstrap peer address (IP:PORT)")
    args = parser.parse_args()
    
    info("Starting Archipel Node...")
    node = Node(f"archipel-node-{args.port}", tcp_port=args.port, bootstrap_peer=args.peer)
    
    info(f"Node ID: {node.node_id.hex()[:16]}...")
    info(f"Using TCP port: {args.port}")
    if args.peer:
        info(f"Bootstrap peer: {args.peer}")
    
    try:
        # Start the node and discovery
        await node.start()
        success("Node initialized and discovery started!")
        info("Node is ready. Waiting for connections...")
        
        # Keep the node running
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        info("Shutting down...")
    finally:
        await node.stop()
        # Small sleep to allow transports to close
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
