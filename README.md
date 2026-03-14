# Archipel

_P2P Encrypted Decentralized Protocol - Zero Internet, Zero Central Authority_

> **Hackathon LBS — Février 2026**  
> Réseau local souverain, chiffré bout-en-bout, sans Internet ni serveur central
> **Status**: 24h Hackathon (Feb 2026)  
> **Language**: Python 3.11+  
> **License**: MIT

---

## 📋 Mission

Archipel est un protocole de communication pair-à-pair fonctionnant **sans infrastructure** :
- ✅ Pas d'Internet obligatoire
- ✅ Pas de serveur central
- ✅ Pas d'autorité de certification (CA)
- ✅ Chiffrement end-to-end sur tous les messages
- ✅ Découverte pair-à-pair automatique via UDP Multicast
- ✅ Transfert de fichiers décentralisé (style BitTorrent)

Chaque nœud est à la fois client et serveur. Le réseau survit à une coupure totale d'infrastructure.

---

## � Project Structure

```
archipel-team/
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── setup.py                  # Package setup
├── README.md                 # This file
│
├── src/
│   ├── crypto/               # Encryption & authentication
│   │   ├── pki.py            # Ed25519 keypair generation
│   │   ├── handshake.py      # Noise Protocol handshake
│   │   ├── session.py        # AES-256-GCM symmetric encryption
│   │   ├── trust.py          # Web of Trust + TOFU
│   │   └── utils.py          # HMAC, HKDF, SHA-256 helpers
│   │
│   ├── network/              # P2P networking (UDP + TCP)
│   │   ├── multicast.py      # UDP Multicast discovery
│   │   ├── tcp_server.py     # Async TCP server
│   │   ├── tcp_client.py     # TCP client connections
│   │   ├── peer_table.py     # Peer routing table (SQLite)
│   │   └── constants.py      # Network constants
│   │
│   ├── transfer/             # File transfer with chunking
│   │   ├── chunking.py       # Split/merge 512KB chunks
│   │   ├── manifest.py       # Build/parse manifest JSON
│   │   ├── downloader.py     # Rarest First + parallel pipeline
│   │   ├── uploader.py       # Chunk upload server
│   │   ├── storage.py        # SQLite index + filesystem
│   │   └── scheduler.py      # Download orchestration
│   │
│   ├── messaging/            # Chat + AI
│   │   ├── chat.py           # E2E encrypted messages
│   │   └── gemini.py         # Gemini API integration
│   │
│   ├── cli/                  # Command-line interface
│   │   ├── commands.py       # Click command decorators
│   │   ├── ui.py             # Rich console output
│   │   └── autocomplete.py   # Tab completion
│   │
│   ├── protocol/             # Packet specification
│   │   ├── packet.py         # Build/parse Archipel packets
│   │   ├── types.py          # Packet type constants
│   │   └── constants.py      # MAGIC, sizes, formats
│   │
│   └── core/                 # Application core
│       ├── node.py           # Main Node class
│       ├── config.py         # Environment loading
│       ├── logger.py         # Loguru configuration
│       └── exceptions.py     # Custom exceptions
│
├── tests/                    # Unit and integration tests
│   ├── test_crypto/
│   ├── test_network/
│   ├── test_transfer/
│   ├── test_messaging/
│   └── test_protocol/
│
├── scripts/                  # Helper scripts
│   ├── generate_keys.py      # Ed25519 key generation
│   └── generate_test_file.py # 50MB test file generator
│
└── demo/                     # Demo scenarios
    ├── scenario_1_discovery.sh
    ├── scenario_2_e2e_chat.sh
    └── scenario_3_file_transfer.sh
```

---

## 🛠 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Crypto** | PyNaCl, PyCryptodome | Ed25519, X25519, AES-256-GCM |
| **Network** | asyncio, socket | UDP Multicast + TCP |
| **Storage** | SQLite3 | Peer table, chunk index |
| **Format** | msgpack | Binary serialization |
| **CLI** | Click, Rich | Interactive interface |
| **AI** | google-generativeai | Optional Gemini integration |
| **Logging** | loguru | Advanced logging |
| **Testing** | pytest, pytest-asyncio | Unit & async tests |

### Pourquoi UDP Multicast + TCP ?

| Techno | Usage | Raison |
|--------|-------|--------|
| **UDP Multicast** | Découverte de pairs | Broadcast efficace sur LAN |
| **TCP Sockets** | Transfert de données | Fiable, contrôle de flux |

**Adresse multicast** : `239.255.42.99:6000`  
**Port TCP par défaut** : `7777`

---

##  Architecture



┌─────────────────────────────────────────────────────────────┐
│ ARCHIPEL NETWORK │
├─────────────────────────────────────────────────────────────┤
│ │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ NODE A │─────│ NODE B │─────│ NODE C │ │
│ │ │ │ │ │ │ │
│ │ Ed25519 │ │ Ed25519 │ │ Ed25519 │ │
│ │ PKI │ │ PKI │ │ PKI │ │
│ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│ │ │ │ │
│ └────────────────┴────────────────┘ │
│ │
│ UDP Multicast (239.255.42.99:6000) │
│ Découverte automatique de pairs │
│ │
│ TCP Sockets (port 7777) │
│ Transfert de données chiffrées │
│ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ MODULES PAR COUCHE │
├─────────────────────────────────────────────────────────────┤
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│ │ CLI/UI │ │ Messaging │ │ Transfer │ │
│ │ │ │ │ │ │ │
│ │ archipel │ │ Chat E2E │ │ Chunking │ │
│ │ commands │ │ Gemini AI │ │ BitTorrent │ │
│ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │
│ │ │ │ │
│ └─────────────────┴─────────────────┘ │
│ │ │
│ ┌────────▼────────┐ │
│ │ Core Node │ │
│ │ │ │
│ │ Peer Table │ │
│ │ Session Mgr │ │
│ └────────┬────────┘ │
│ │ │
│ ┌─────────────────┴─────────────────┐ │
│ │ │ │
│ ┌──────▼───────┐ ┌───────▼──────┐ │
│ │ Crypto │ │ Network │ │
│ │ │ │ │ │
│ │ Ed25519 │ │ UDP Multicast│ │
│ │ X25519 │ │ TCP Server │ │
│ │ AES-256-GCM │ │ Peer Disc. │ │
│ │ HMAC-SHA256 │ │ Routing │ │
│ └──────────────┘ └──────────────┘ │
│ │
└─────────────────────────────────────────────────────────────┘
12345

---



### Types de paquets

| Valeur | Type | Usage |
|--------|------|-------|
| `0x01` | HELLO | Annonce de présence |
| `0x02` | PEER_LIST | Liste des nœuds connus |
| `0x03` | MSG | Message chiffré |
| `0x04` | CHUNK_REQ | Requête chunk |
| `0x05` | CHUNK_DATA | Données chunk |
| `0x06` | MANIFEST | Métadonnées fichier |
| `0x07` | ACK | Acquittement |

### Exemple : Paquet HELLO (73 bytes)
Modifier par Florent
