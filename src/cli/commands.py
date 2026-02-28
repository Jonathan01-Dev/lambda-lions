"""Click command decorators for CLI."""

import click


@click.command()
@click.option('--name', prompt='Your name', help='Name to display')
def hello(name):
    """Simple hello command."""
    click.echo(f"Hello {name}!")


@click.group()
def cli():
    """Archipel P2P Network CLI."""
    pass


from rich.table import Table
from src.cli.ui import console
from src.network.peer_table import PeerTable

@cli.command()
@click.option('--port', default=7777, help='Port of the node to check')
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


@cli.command()
@click.option('--port', default=7777, help='Your local node port')
@click.option('--peer', required=True, help='Peer address to connect to (IP:PORT)')
def connect(port, peer):
    """Manually connect and handshake with a peer."""
    import asyncio
    from src.core.node import Node
    from src.network.tcp_client import TCPClient
    
    async def _connect():
        node = Node(f"cli-node-{port}", tcp_port=port)
        host, p = peer.split(":")
        console.print(f"[info]Connecting to {peer}...[/info]")
        client = TCPClient(node, host, int(p))
        try:
            await client.send_encrypted(b"CLI Greeting")
            await client.close()
            console.print(f"[success]Connection and handshake with {peer} successful![/success]")
        except Exception as e:
            console.print(f"[error]Failed to connect to {peer}: {e}[/error]")

    asyncio.run(_connect())


@cli.command()
@click.option('--port', default=7777, help='Your local node port')
@click.option('--peer-id', required=True, help='Hex Node ID of the recipient')
@click.option('--message', required=True, help='Message to send')
def send(port, peer_id, message):
    """Send an encrypted message to a discovered peer."""
    import asyncio
    from src.core.node import Node
    
    async def _send():
        node = Node(f"cli-node-{port}", tcp_port=port)
        console.print(f"[info]Sending message to {peer_id[:16]}...[/info]")
        try:
            await node.send_to_peer(peer_id, message.encode())
            console.print(f"[success]Message sent successfully![/success]")
        except Exception as e:
            console.print(f"[error]Failed to send message: {e}[/error]")

    asyncio.run(_send())


cli.add_command(peers)
cli.add_command(connect)
cli.add_command(send)
cli.add_command(hello)

if __name__ == "__main__":
    cli()
