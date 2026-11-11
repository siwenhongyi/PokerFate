"""Headless game client: play without the real client or a device.

Replaces the MITM chain (DNS hijack + certs + mitmweb + proxy) with a direct
WSS connection, resuming a session harvested from one real device login
(data/headless_session.json, git-ignored — see harvest_session) instead of
performing /login itself:

    resume data/headless_session.json -> uid, rdkey, authorization, server list
    WSS  pb.UserLoginREQ        -> pb.UserLoginRSP
    WSS  pb.HeartBeatREQ / 5s   -> keep-alive (server drops after 2 misses)
    WSS  pb.QuickStartREQ       -> server seats us; from there BotBridge drives
                                   the hand exactly as it did behind the proxy.

Modules:
    harvest_session  standalone entry point that captures/refreshes the
                      session file from one real device login (run this
                      first, and again whenever the saved session expires)
    login            LoginResult/ServerEntry types + /ping latency probe
    session          WSS session driver around BotBridge
"""
