# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Secret redaction for log/error output.

Auth flows shuttle tokens and STS secrets around; any of them can end up in an
exception body or a debug print. :func:`redact` scrubs the high-entropy strings
(JWTs, bearer/STS tokens, ``ak/sk`` style secrets) before they are surfaced.
"""

from __future__ import annotations

import re

# JWTs: three base64url segments separated by dots.
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
# Volcengine STS / access tokens and long opaque secrets: long url-safe runs
# are only candidates — well-known identifier shapes (UUIDs, trace/git/digest
# hex ids, filesystem paths, plain words/numbers) are spared by
# _redact_opaque, otherwise error logs lose the very ids needed to debug them.
_OPAQUE_CANDIDATE = re.compile(r"\b[A-Za-z0-9/+_-]{20,}={0,2}\b")
_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)
_HEX = re.compile(r"[0-9a-fA-F]+\Z")
# OTel trace_id (32), git sha (40), sha256 digest (64). Labeled hex secrets
# are still caught by _FIELD regardless of shape.
_HEX_ID_LENGTHS = frozenset({32, 40, 64})
# Explicit secret-bearing query/JSON/header fields. secret_access_key is listed
# before secret_key so the longer name wins at a shared position; signature
# covers presigned-URL HMACs whose 64-hex value _redact_opaque otherwise spares.
_FIELD = re.compile(
    r"(?i)(\"?(?:access_token|refresh_token|id_token|client_secret|secret_access_key"
    r"|secret_key|secretkey|accesskeyid|accesskey|sessiontoken|session_token"
    r"|security_token|signature|authorization"
    r"|apikey|api_key|token|password)\"?\s*[:=]\s*\"?(?:bearer\s+)?)"
    r"([^\"&\s,}]+)"
)


def _redact_opaque(match: re.Match) -> str:
    token = match.group(0)
    if _UUID.match(token):
        return token
    if len(token) in _HEX_ID_LENGTHS and _HEX.match(token):
        return token
    has_alpha = any(c.isalpha() for c in token)
    has_digit = any(c.isdigit() for c in token)
    if not (has_alpha and has_digit):
        # Long plain words and long numbers are identifiers, not key material.
        return token
    if "/" in token and len(token) < 64 and not token.endswith("="):
        # Filesystem-path shaped; base64 blobs containing slashes are either
        # padded or far longer than any path segment run.
        return token
    return "***"


def redact(text: str) -> str:
    """Return ``text`` with credential-looking substrings replaced by ``***``."""
    if not text:
        return text
    text = _FIELD.sub(lambda m: m.group(1) + "***", text)
    text = _JWT.sub("***", text)
    text = _OPAQUE_CANDIDATE.sub(_redact_opaque, text)
    return text


def mask(secret: str | None, *, keep: int = 4) -> str:
    """Mask a secret, keeping only the last ``keep`` characters for recognition."""
    if not secret:
        return "<none>"
    if len(secret) <= keep:
        return "*" * len(secret)
    return "*" * (len(secret) - keep) + secret[-keep:]
