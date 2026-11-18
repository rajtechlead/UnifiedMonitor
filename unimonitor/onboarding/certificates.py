"""Self-signed client certificates for the Entra app registration.

A certificate credential is the safer default for an app registration: there is no
guessable string in a database, its lifetime is explicit, and Entra lets it expire
instead of leaking. The setup wizard generates the key pair, uploads the public
certificate to the app it just created, and signs client assertions with the key —
the same thing a manual "Certificates & secrets → Upload certificate" would do.

Microsoft caps certificate validity at 10 years; the wizard defaults to one year.
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

LOGIN_BASE = "https://login.microsoftonline.com"

DEFAULT_VALIDITY_DAYS = 365
MIN_VALIDITY_DAYS = 1
MAX_VALIDITY_DAYS = 1095


def clamp_validity_days(days: int | None) -> int:
    """Keep a user-supplied lifetime inside what Entra accepts."""
    if not days or days < MIN_VALIDITY_DAYS:
        return DEFAULT_VALIDITY_DAYS
    return min(int(days), MAX_VALIDITY_DAYS)


def _der_bytes(certificate_pem: str) -> bytes:
    """Accept a PEM certificate or a bare base64 DER blob."""
    text = (certificate_pem or "").strip()
    if "BEGIN CERTIFICATE" in text:
        return x509.load_pem_x509_certificate(text.encode()).public_bytes(serialization.Encoding.DER)
    return base64.b64decode("".join(text.split()))


def _sha1_digest(data: bytes) -> bytes:
    """SHA-1 digest — the certificate-thumbprint format Entra and JWT `x5t` require."""
    # SHA-1 is fixed by the protocol (Entra thumbprint, JWT x5t), not a security choice.
    return hashlib.sha1(data).digest()  # noqa: S324  # NOSONAR


def thumbprint(certificate_pem: str) -> str:
    """SHA-1 thumbprint as Entra shows it (uppercase hex)."""
    return _sha1_digest(_der_bytes(certificate_pem)).hex().upper()


def thumbprint_b64(certificate_pem: str) -> str:
    """The same digest as Graph returns it in `keyCredentials.customKeyIdentifier`."""
    return base64.b64encode(_sha1_digest(_der_bytes(certificate_pem))).decode()


def expiry(certificate_pem: str) -> datetime:
    """When an uploaded certificate stops being accepted."""
    return x509.load_pem_x509_certificate(certificate_pem.strip().encode()).not_valid_after_utc


@dataclass(frozen=True)
class ClientCertificate:
    private_key_pem: str
    certificate_pem: str
    certificate_b64: str
    thumbprint: str
    not_after: datetime

    @property
    def not_after_iso(self) -> str:
        return self.not_after.replace(microsecond=0).isoformat()

    def files(self, base_name: str = "unimonitor-client") -> list[dict[str, str]]:
        """The files an administrator needs for the manual-upload fallback."""
        return [
            {"name": f"{base_name}.key.pem", "label": "Private key — keep it secret", "content": self.private_key_pem},
            {"name": f"{base_name}.crt.pem", "label": "Certificate (PEM)", "content": self.certificate_pem},
            {"name": f"{base_name}.cer", "label": "Certificate for the Entra portal", "content": self.certificate_b64},
        ]


def generate_client_certificate(common_name: str = "UniMonitor", validity_days: int | None = None) -> ClientCertificate:
    """Mint a self-signed RSA certificate that Entra will accept as a credential."""
    days = clamp_validity_days(validity_days)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, (common_name or "UniMonitor")[:64])])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        # A little clock skew at the start; Entra compares against its own clock.
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(key, hashes.SHA256())
    )
    der = certificate.public_bytes(serialization.Encoding.DER)
    return ClientCertificate(
        private_key_pem=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode(),
        certificate_b64=base64.b64encode(der).decode(),
        thumbprint=_sha1_digest(der).hex().upper(),
        not_after=certificate.not_valid_after_utc,
    )


def graph_key_credential(cert: ClientCertificate, display_name: str = "unimonitor-setup") -> dict[str, str]:
    """The `keyCredential` body Graph's `addKey` action expects."""
    return {
        "type": "AsymmetricX509Cert",
        "usage": "Verify",
        "key": cert.certificate_b64,
        "displayName": display_name,
    }


def client_assertion(
    client_id: str,
    tenant_id: str,
    private_key_pem: str,
    certificate_pem: str,
    *,
    authority: str = LOGIN_BASE,
    lifetime_seconds: int = 600,
) -> str:
    """Sign the JWT Entra accepts in place of a client secret."""
    der = _der_bytes(certificate_pem)
    header = {
        "alg": "RS256",
        "typ": "JWT",
        "x5t": base64.urlsafe_b64encode(_sha1_digest(der)).decode().rstrip("="),
    }
    now = int(time.time())
    claims = {
        "aud": f"{authority}/{tenant_id}/oauth2/v2.0/token",
        "exp": now + lifetime_seconds,
        "iat": now,
        "nbf": now,
        "iss": client_id,
        "sub": client_id,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, private_key_pem, algorithm="RS256", headers=header)


def certificate_credential(private_key_pem: str, certificate_pem: str) -> dict[str, str]:
    """The credential dict MSAL uses to authenticate with a certificate."""
    return {
        "private_key": private_key_pem,
        "thumbprint": thumbprint(certificate_pem),
        "public_certificate": certificate_pem,
    }
