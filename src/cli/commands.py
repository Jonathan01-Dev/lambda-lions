"""Advanced CLI for Archipel P2P Network."""

import click
import asyncio
from rich.table import Table
from src.cli.ui import console, info, success, error
from src.network.peer_table import PeerTable
from src.core.node import Node
from main import run_node


@click.group()
def cli():
    """Archipel P2P Network - Zero-Internet Decentralized OS."""
    pass


# --- KEYS GROUP ---
@cli.group()
def keys():
    """Identity and cryptographic key management."""
    pass


@keys.command()
def show():
    """Show your local Node ID and Public Key."""
    # We initialize a temporary node to get the keys
    node = Node(node_name="temp")
    node_id = node.node_id.hex()
    console.print(f"\n[bold green]Your Archipel Identity[/bold green]")
    console.print(f"Node ID (Full):  [cyan]{node_id}[/cyan]")
    console.print(f"Node ID (Short): [bold]{node_id[:16]}[/bold]")
    console.print(f"Public Key:      [magenta]{node.vk.encode().hex()}[/magenta]")
    
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    console.print(f"Local IP:        [yellow]{IP}[/yellow]\n")


# --- NODE GROUP ---
@cli.group()
def node():
    """P2P Node management and discovery."""
    pass


@node.command(name="start")
@click.option('--port', default=7777, help='TCP port to listen on')
@click.option('--peer', help='Bootstrap peer address (IP:PORT)')
def node_start(port, peer):
    """Start the P2P node and join the network."""
    from src.core.logger import setup_logging
    setup_logging()
    try:
        asyncio.run(run_node(port, peer))
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option('--port', default=7777, help='TCP port to listen on')
@click.option('--peer', help='Bootstrap peer address (IP:PORT)')
def dashboard(port, peer):
    """Launch the Archipel Dashboard (TUI)."""
    from src.cli.tui import ArchipelDashboard
    app = ArchipelDashboard(port=port, peer=peer)
    app.run()


@node.command()
@click.option('--port', default=7777, help='Port of the node database to query')
def peers(port):
    """List all discovered peers."""
    db_path = f"peer_table_{port}.db"
    pt = PeerTable(db_path)
    peers_list = pt.list_peers()
    
    if not peers_list:
        console.print("[yellow]No peers found in this node's table.[/yellow]")
        return
        
    table = Table(title=f"Peers discovered by node on port {port}")
    table.add_column("Node ID", style="cyan")
    table.add_column("Host", style="magenta")
    table.add_column("Port", style="green")
    
    for node_id, host, p in peers_list:
        table.add_row(node_id[:16] + "...", host, str(p))
        
    console.print(table)


# --- CHAT GROUP ---
@cli.group()
def chat():
    """Direct encrypted messaging between peers."""
    pass


@chat.command()
@click.option('--port', default=7777, help='Your local node port')
@click.option('--peer', required=True, help='Peer address to connect to (IP:PORT)')
def connect(port, peer):
    """Manually handshake with a peer."""
    from src.network.tcp_client import TCPClient
    
    async def _connect():
        n = Node(f"cli-node-{port}", tcp_port=port)
        host, p = peer.split(":")
        console.print(f"[info]Connecting to {peer}...[/info]")
        client = TCPClient(n, host, int(p))
        try:
            await client.send_encrypted(b"CLI Handshake Request")
            await client.close()
            console.print(f"[success]Handshake with {peer} successful![/success]")
        except Exception as e:
            console.print(f"[error]Failed to connect: {e}[/error]")

    asyncio.run(_connect())


@chat.command()
@click.option('--port', default=7777, help='Your local node port')
@click.option('--peer-id', required=True, help='Hex Node ID of the recipient')
@click.option('--message', required=True, help='Message to send')
def send(port, peer_id, message):
    """Send an encrypted message to a peer."""
    async def _send():
        n = Node(f"cli-node-{port}", tcp_port=port)
        console.print(f"[info]Sending message to {peer_id[:16]}...[/info]")
        try:
            await n.send_to_peer(peer_id, message.encode())
            console.print(f"[success]Message sent successfully![/success]")
        except Exception as e:
            console.print(f"[error]Failed to send: {e}[/error]")

    asyncio.run(_send())


if __name__ == "__main__":
    cli()
