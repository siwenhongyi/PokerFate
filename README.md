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

### 4. Configure

Edit `pf_intercept/config.py`:

```python
SERVER_HOST = "zga-entry.poker-fate.net"   # WSS hostname the game connects to
```

The proxy auto-detects seat ID and blind sizes from game messages.
The real server IP is resolved at startup via external DNS (8.8.8.8), bypassing the local hosts file.

### 5. Redirect game traffic (Windows hosts file)

Add to `C:\Windows\System32\drivers\etc\hosts` (run as Administrator):

```
127.0.0.1  zga-entry.poker-fate.net
```

### 6. Run the proxy

```bash
python -m pf_intercept.proxy
```

## Optional: capture HTTP login response for dynamic server discovery

Run mitmweb alongside the proxy to intercept the HTTP login response and auto-discover the actual WSS server:

```bash
mitmweb --listen-port 8080 --ignore-hosts "aliyuncs.com|miui.com" -s pf_reverse/force_domain.py
```

Set the system HTTP proxy to `127.0.0.1:8080`. When the login response is captured, `pf_intercept/discovered_server.json` is written and the proxy uses it on next startup.

## Architecture

```
Game (Windows)
  │  hosts file → 127.0.0.1
  │
pf_intercept/proxy.py  :9012  (TLS — our cert)
  │  decode protobuf frames
  │  drive bot via pokerfate/api.py
  │  inject ActionREQ when it's our turn
  │
Real game server  wss://zga-entry.poker-fate.net:9012
```

## Card encoding

```
code = rank + suit * 256
rank : 2='2' … 14='A'
suit : 0='d'  1='c'  2='h'  3='s'
```
