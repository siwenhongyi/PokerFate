"""
Generate a local CA and a server certificate for the game server hostname.

Usage:
    python -m pf_intercept.gen_cert

Output (in pf_intercept/certs/):
    ca.crt          ← install this into Windows Trusted Root CA (double-click → install)
    server.crt      ← used by proxy (TLS server cert)
    server.key      ← used by proxy (TLS server private key)

Requires:
    pip install cryptography
"""

import datetime
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pf_intercept.config import SERVER_HOST, CERTS_DIR


def _gen_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _save_key(key, path: Path) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def _save_cert(cert, path: Path) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def generate(server_host: str, certs_dir: Path) -> None:
    certs_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(datetime.timezone.utc)
    ten_years = now + datetime.timedelta(days=3650)

    # ── CA ──────────────────────────────────────────────────────────────────
    ca_key = _gen_key()
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "PokerFate Local CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pf_intercept"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(ten_years)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    _save_key(ca_key,   certs_dir / "ca.key")
    _save_cert(ca_cert, certs_dir / "ca.crt")
    print(f"CA cert   : {certs_dir / 'ca.crt'}")

    # ── Server cert (signed by our CA) ──────────────────────────────────────
    srv_key = _gen_key()

    # SAN: add the hostname; also add 127.0.0.1 as IP SAN just in case
    san_list: list[x509.GeneralName] = [x509.DNSName(server_host)]
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address(server_host)))
    except ValueError:
        pass   # not an IP, fine
    san_list.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))

    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, server_host)]))
        .issuer_name(ca_cert.subject)
        .public_key(srv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(ten_years)
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    _save_key(srv_key,   certs_dir / "server.key")
    _save_cert(srv_cert, certs_dir / "server.crt")
    print(f"Server cert: {certs_dir / 'server.crt'}")
    print()
    print("Next step (Windows):")
    print(f"  1. Copy {certs_dir / 'ca.crt'} to the Windows machine")
    print(f"  2. Double-click ca.crt → Install Certificate → Local Machine → Trusted Root CAs")
    print(f"  3. Add to hosts:  127.0.0.1  {server_host}")
    print(f"  4. Run proxy:     python -m pf_intercept.proxy")


if __name__ == "__main__":
    generate(SERVER_HOST, Path(CERTS_DIR))
