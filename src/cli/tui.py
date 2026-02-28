"""Premium TUI for Archipel P2P Network using Textual."""

import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, ListView, ListItem, Label, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive

import socket
from src.core.node import Node
from src.network.peer_table import PeerTable

def get_lan_ip():
    """Get the local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class ArchipelDashboard(App):
    """A Textual app to manage Archipel Node."""

    CSS = """
    Screen {
        background: #1a1b26;
    }

    #sidebar {
        width: 30%;
        border-right: solid #3b4261;
        background: #16161e;
    }

    #chat-area {
        width: 70%;
    }

    .peer-item {
        padding: 1 2;
        border-bottom: solid #24283b;
    }

    .peer-selected {
        background: #2ac3de;
        color: #1a1b26;
    }

    #msg-log {
        height: 1fr;
        border: solid #3b4261;
        margin: 1;
        background: #1a1b26;
    }

    #input-area {
        height: auto;
        dock: bottom;
        padding: 1;
    }

    Input {
        border: tall #2ac3de;
        background: #16161e;
    }

    Header {
        background: #24283b;
        color: #c0caf5;
        text-style: bold;
    }

    Footer {
        background: #16161e;
    }

    Label {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("c", "connect_manual", "Connect Ad-hoc", show=True),
        Binding("r", "refresh_peers", "Refresh Peers", show=True),
        Binding("f", "transfer_file", "Send File", show=True),
        Binding("a", "ask_gemini", "Ask AI", show=True),
    ]

    selected_peer_id = reactive(None)

    def __init__(self, port=7777, peer=None):
        super().__init__()
        self.port = port
        self.bootstrap_peer = peer
        self.node = None
        self.peer_refresh_task = None

    def on_mount(self):
        """Start the node when the app starts."""
        asyncio.create_task(self.start_node())
        self.peer_refresh_task = self.set_interval(5, self.update_peer_list)

    async def start_node(self):
        """Initialize and start the P2P node."""
        try:
            self.node = Node(f"tui-node-{self.port}", tcp_port=self.port, bootstrap_peer=self.bootstrap_peer)
            
            # Monkey patch on_message_received to update TUI
            original_on_message = self.node.on_message_received
            
            def patched_on_message(sender_id, data):
                msg = data.decode(errors='replace')
                # Use call_from_thread to ensure thread safety if needed, 
                # although textual is async, the callback might come from a task
                self.call_from_thread(self.write_to_log, f"[cyan]{sender_id[:8]}[/cyan]: {msg}")
                
                # Auto-select if nothing is selected
                if not self.selected_peer_id:
                    self.selected_peer_id = sender_id
                    self.call_from_thread(self.update_peer_list)

                original_on_message(sender_id, data)
                
            self.node.on_message_received = patched_on_message
            
            await self.node.start()
            lan_ip = get_lan_ip()
            self.title = f"Archipel Node | ID: {self.node.node_id.hex()[:16]}... | IP: {lan_ip}:{self.port}"
            self.write_to_log("[bold green]System[/bold green]: Node started and ready.")
            self.write_to_log(f"[bold blue]Hint[/bold blue]: To connect another PC, type: [italic]/connect {lan_ip}:{self.port}[/italic] on the other machine.")
        except OSError as e:
            if "address already in use" in str(e).lower() or "10048" in str(e):
                self.write_to_log(f"[bold red]CRITICAL ERROR[/bold red]: Port {self.port} is already in use!")
                self.write_to_log("Please use another port: [italic]python -m src.cli.commands dashboard --port 7778[/italic]")
            else:
                self.write_to_log(f"[bold red]Failed to start node[/bold red]: {e}")
        except Exception as e:
            self.write_to_log(f"[bold red]Error[/bold red]: {e}")

    def write_to_log(self, message: str):
        """Helper to write to RichLog with auto-render."""
        try:
            log = self.query_one("#msg-log", RichLog)
            log.write(message)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Horizontal():
                with Vertical(id="sidebar"):
                    yield Label("[bold cyan]PEERS DISCOVERED[/bold cyan]", id="peer-header")
                    yield ListView(id="peer-list")
                with Vertical(id="chat-area"):
                    yield RichLog(id="msg-log", highlight=True, markup=True, max_lines=1000)
                    yield Container(
                        Input(placeholder="Type message and press Enter...", id="chat-input"),
                        id="input-area"
                    )
        yield Footer()

    def update_peer_list(self):
        """Refresh the list of peers from the database."""
        if not self.node:
            return
            
        peers = self.node.peer_table.list_peers()
        list_view = self.query_one("#peer-list", ListView)
        
        # Store current selection
        current_selection = list_view.index
        
        list_view.clear()
        for node_id, host, port in peers:
            list_view.append(ListItem(Label(f"Node: {node_id[:8]} ({host}:{port})"), id=f"peer-{node_id}"))
            
        if current_selection is not None and current_selection < len(list_view):
            list_view.index = current_selection
        elif len(list_view) > 0 and self.selected_peer_id is None:
            # Auto-select first peer if none selected
            list_view.index = 0
            self.selected_peer_id = peers[0][0]

    def on_list_view_selected(self, event: ListView.Selected):
        """Update selected peer ID when a list item is chosen."""
        if event.item and event.item.id:
            self.selected_peer_id = event.item.id.replace("peer-", "")
            self.write_to_log(f"[bold yellow]Chatting with {self.selected_peer_id[:8]}[/bold yellow]")

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle input for both chat and manual connection."""
        text = event.value.strip()
        if not text:
            return
            
        event.input.value = ""
        
        if text.startswith("/connect "):
            peer_addr = text.replace("/connect ", "").strip()
            self.write_to_log(f"[bold yellow]Ad-hoc[/bold yellow]: Connecting to {peer_addr}...")
            try:
                from src.network.tcp_client import TCPClient
                if ":" in peer_addr:
                    host, port = peer_addr.split(":", 1)
                else:
                    host = peer_addr
                    port = 7777
                client = TCPClient(self.node, host, int(port))
                peer_id = await client.connect() # This will also add it to the table
                await client.close()
                self.selected_peer_id = peer_id
                self.write_to_log(f"[bold green]Success[/bold green]: Handshake with {host}:{port} complete.")
                self.update_peer_list()
                
                # Highlight in list
                list_view = self.query_one("#peer-list", ListView)
                for i, item in enumerate(list_view.children):
                    if item.id == f"peer-{peer_id}":
                        list_view.index = i
                        break
            except Exception as e:
                self.write_to_log(f"[bold red]Connect Failed[/bold red]: {e}")
            return

        elif text.startswith("/gemini ") or text.startswith("/ask ") or text.startswith("@archipel-ai "):
            prompt = text.replace("/gemini ", "").replace("/ask ", "").replace("@archipel-ai ", "")
            self.write_to_log(f"[bold magenta]Gemini[/bold magenta]: Querying...")
            try:
                from src.messaging.gemini import GeminiIntegration
                gemini = GeminiIntegration()
                import threading
                def run_query():
                    response = gemini.query(prompt)
                    self.call_from_thread(self.write_to_log, f"[bold magenta]Gemini[/bold magenta]: {response}")
                threading.Thread(target=run_query, daemon=True).start()
            except Exception as e:
                self.write_to_log(f"[bold red]Gemini Failed[/bold red]: {e}")
            return

        elif text.startswith("/sendfile "):
            filepath = text.replace("/sendfile ", "").strip()
            if not self.selected_peer_id:
                self.write_to_log("[bold red]Error[/bold red]: Select a peer first to send a file to.")
                return
            
            import os
            if not os.path.exists(filepath):
                self.write_to_log(f"[bold red]File not found[/bold red]: {filepath}")
                return
                
            self.write_to_log(f"[bold yellow]Transfer[/bold yellow]: Sending '{filepath}' to {self.selected_peer_id[:8]} [italic](Chunked)...[/italic]")
            try:
                # Use the new chunked transfer logic
                asyncio.create_task(self.node.send_file(self.selected_peer_id, filepath))
                self.write_to_log(f"[bold green]System[/bold green]: Manifest sent. Transfer in progress.")
            except Exception as e:
                self.write_to_log(f"[bold red]Transfer Failed[/bold red]: {e}")
            return

        if not self.selected_peer_id:
            self.write_to_log("[bold red]Error[/bold red]: Select a peer first or use [italic]/connect IP:PORT[/italic]")
            return
            
        try:
            self.write_to_log(f"[bold green]Me[/bold green]: {text}")
            from src.protocol.packet import Packet
            from src.protocol import types
            packet = Packet(types.MSG, self.node.node_id, text.encode())
            await self.node.send_to_peer(self.selected_peer_id, packet.serialize())
        except Exception as e:
            self.write_to_log(f"[bold red]Send Failed[/bold red]: {e}")

    def action_connect_manual(self):
        """Prepare the input for manual connection."""
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = "/connect "
        input_widget.focus()

    def action_transfer_file(self):
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = "/sendfile "
        input_widget.focus()

    def action_ask_gemini(self):
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = "/ask "
        input_widget.focus()

    async def action_quit(self):
        """Gracefully stop node and exit."""
        if self.node:
            await self.node.stop()
        self.exit()

if __name__ == "__main__":
    app = ArchipelDashboard()
    app.run()
