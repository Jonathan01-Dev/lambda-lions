import argparse
import sys
import asyncio
from src.core.node import Node
from src.cli.ui import info, success
from src.core.logger import setup_logging


async def run_node(port=7777, peer=None):
    """Run the Archipel node with given parameters."""
    info("Starting Archipel Node...")
    node = Node(f"archipel-node-{port}", tcp_port=port, bootstrap_peer=peer)
    
    info(f"Node ID: {node.node_id.hex()[:16]}...")
    info(f"Using TCP port: {port}")
    
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    info(f"Local IP Address: {IP}")
    if peer:
        info(f"Bootstrap peer: {peer}")
    
    try:
        # Start the node and discovery
        await node.start()
        success("Node initialized and discovery started!")
        info("Node is ready. Waiting for connections...")
        
        # Keep the node running
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        info("Shutdown: Received KeyboardInterrupt (Ctrl+C).")
    except asyncio.CancelledError:
        info("Shutdown: Asyncio Task/Loop Cancelled.")
    except Exception as e:
        error(f"Unexpected error causing shutdown: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        info("Closing node resources...")
        await node.stop()
        info("Node stopped.")
        # Small sleep to allow transports to close
        await asyncio.sleep(0.1)


async def main():
    """Initialize and run the node from CLI args."""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Archipel P2P Node")
    parser.add_argument("--port", type=int, default=7777, help="TCP port to listen on")
    parser.add_argument("--peer", type=str, help="Bootstrap peer address (IP:PORT)")
    args = parser.parse_args()
    
    await run_node(args.port, args.peer)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
