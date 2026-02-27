# Archipel

Protocole P2P Chiffré et Décentralisé à Zéro-Connexion

> **Hackathon LBS — Février 2026**  
> Réseau local souverain, chiffré bout-en-bout, sans Internet ni serveur central

---

##  Mission

Archipel est un protocole de communication pair-à-pair fonctionnant **sans infrastructure** :
-  Pas d'Internet
-  Pas de serveur central  
-  Pas d'autorité de certification

Chaque nœud est à la fois client et serveur. Le réseau survit à une coupure totale d'infrastructure.

---

## 🛠 Stack Technique

### Langage : Python 3.11+

**Pourquoi Python ?**
- Développement rapide (24h c'est court)
- Bibliothèques crypto matures (PyNaCl, PyCryptodome)
- AsyncIO natif pour gestion concurrente
- Debugging facile pendant la démo

### Architecture par couche

| Couche | Technologie | Rôle |
|--------|-------------|------|
| **Crypto** | PyNaCl + PyCryptodome | Ed25519, X25519, AES-256-GCM |
| **Réseau** | `socket` + `asyncio` | UDP Multicast + TCP |
| **Stockage** | SQLite3 | Peer table + index chunks |
| **Sérialisation** | msgpack | Binaire compact |
| **CLI** | Click + Rich | Interface démo |
| **AI** | google-generativeai | Gemini (optionnel) |

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
