from __future__ import annotations

import logging

log = logging.getLogger("pf_proxy")


def _extract_sni_hostname(data: bytes) -> str | None:
    """Best-effort parse TLS ClientHello SNI hostname from raw bytes."""
    try:
        if len(data) < 5 or data[0] != 0x16:  # TLS handshake record
            return None
        rec_len = int.from_bytes(data[3:5], "big")
        if len(data) < 5 + rec_len:
            return None
        if data[5] != 0x01:  # ClientHello
            return None
        hs_len = int.from_bytes(data[6:9], "big")
        body_start = 9
        body_end = body_start + hs_len
        if body_end > len(data):
            return None
        p = body_start

        p += 2   # version
        p += 32  # random
        if p >= body_end:
            return None

        sid_len = data[p]
        p += 1 + sid_len
        if p + 2 > body_end:
            return None

        cs_len = int.from_bytes(data[p:p + 2], "big")
        p += 2 + cs_len
        if p >= body_end:
            return None

        comp_len = data[p]
        p += 1 + comp_len
        if p + 2 > body_end:
            return None

        ext_len = int.from_bytes(data[p:p + 2], "big")
        p += 2
        ext_end = p + ext_len
        if ext_end > body_end:
            return None

        while p + 4 <= ext_end:
            etype = int.from_bytes(data[p:p + 2], "big")
            elen = int.from_bytes(data[p + 2:p + 4], "big")
            p += 4
            if p + elen > ext_end:
                return None
            if etype == 0x0000:  # server_name
                if elen < 2:
                    return None
                q = p + 2
                list_end = p + elen
                while q + 3 <= list_end:
                    ntype = data[q]
                    nlen = int.from_bytes(data[q + 1:q + 3], "big")
                    q += 3
                    if q + nlen > list_end:
                        return None
                    if ntype == 0:
                        return data[q:q + nlen].decode("ascii", errors="ignore")
                    q += nlen
            p += elen
    except Exception:
        log.exception("[TLS] failed to extract SNI from initial client bytes")
        return None
    return None


def _extract_http_host(data: bytes) -> str | None:
    """Best-effort parse HTTP Host header from raw bytes."""
    try:
        text = data.decode("iso-8859-1", errors="ignore")
        if "\r\n" not in text:
            return None
        lines = text.split("\r\n")
        if not lines or "HTTP/" not in lines[0]:
            return None
        for line in lines[1:]:
            if not line:
                break
            if line.lower().startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        log.exception("[HTTP] failed to extract Host header")
        return None
    return None


def _extract_http_path(data: bytes) -> str | None:
    """Extract request path from a plain HTTP request line."""
    try:
        line = data.split(b"\r\n", 1)[0].decode("iso-8859-1")
        parts = line.split(" ")
        if len(parts) >= 2 and parts[0] in (
            "GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "CONNECT"
        ):
            return parts[1]
    except Exception:
        log.exception("[HTTP] failed to extract request path")
    return None


def _http_host_header(host: str, scheme: str | None, port: int | None) -> str:
    if not port:
        return host
    default = 443 if scheme in ("https", "wss") else 80
    return host if int(port) == default else f"{host}:{int(port)}"


def _rewrite_http_host_header(data: bytes, host_value: str) -> bytes:
    try:
        head, sep, body = data.partition(b"\r\n\r\n")
        if not sep:
            return data
        lines = head.decode("iso-8859-1", errors="ignore").split("\r\n")
        replaced = False
        out: list[str] = []
        for line in lines:
            if line.lower().startswith("host:"):
                out.append(f"Host: {host_value}")
                replaced = True
            else:
                out.append(line)
        if not replaced and out:
            out.insert(1, f"Host: {host_value}")
        return "\r\n".join(out).encode("iso-8859-1") + sep + body
    except Exception:
        log.exception("[HTTP] failed to rewrite Host header")
        return data
