"""Headless game client: play without the real client or a device.

Replaces the MITM chain (DNS hijack + certs + mitmweb + proxy) with a direct
connection to the game servers:

    HTTP POST /login            -> uid, rdkey, authorization, server list
    WSS  pb.UserLoginREQ        -> pb.UserLoginRSP
    WSS  pb.HeartBeatREQ / 5s   -> keep-alive (server drops after 2 misses)
    WSS  pb.QuickStartREQ       -> server seats us; from there BotBridge drives
                                   the hand exactly as it did behind the proxy.

Modules:
    credentials  account file (data/headless_account.json, git-ignored)
    login        HTTP login, mirrors LoginModel.lua + Net.lua addSaltArgs
    session      WSS session driver around BotBridge
"""
