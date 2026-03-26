# PokerFate Bot

Texas Hold'em AI bot for PokerFate, using a WSS MITM proxy to intercept and inject game actions.

## Project Structure

```
pokerfate/          Strategy engine (GTO + exploitative decision making)
pf_intercept/       WSS MITM proxy — intercepts game traffic, drives the bot
pf_reverse/         Reverse engineering artifacts (Lua source, proto files)
```

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Compile protobuf schemas (one-time)

```bash
bash pf_intercept/gen_pb2.sh
```

### 3. Generate TLS certificates (one-time)

```bash
python -m pf_intercept.gen_cert
```

Install `pf_intercept/certs/ca.crt` into the **Windows Trusted Root Certificate Authorities**.

### 4. Redirect game traffic (Windows hosts file, one-time)

Add to `C:\Windows\System32\drivers\etc\hosts` (run Notepad as Administrator):

```
127.0.0.1  zga-entry.poker-fate.net
127.0.0.1  zga-entry.allinmoe.com
127.0.0.1  ga-foreign.poker-fate.com
```

All three entries are required — the game may connect to any of these domains.

### 5. Run the proxy

```bash
python -m pf_intercept.proxy
```

Then open the game. The proxy intercepts whichever domain the game connects to,
resolves the real server IP via external DNS (bypassing the hosts redirect),
and relays traffic transparently.

The proxy auto-detects seat ID and blind sizes from game messages.

## Architecture

```
Game (Windows)
  │  hosts file → 127.0.0.1:<domain>
  │
pf_intercept/proxy.py  :9012  (TLS — our cert)
  │  reads SNI from incoming connection → resolves real IP via external DNS
  │  decode protobuf frames
  │  drive bot via pokerfate/api.py
  │  inject ActionREQ when it's our turn
  │
Real game server  wss://<domain>:9012  (IP from DNS cache)
```

## Card encoding

```
code = rank + suit * 256
rank : 2='2' … 14='A'
suit : 1='d'  2='c'  3='h'  4='s'
```
