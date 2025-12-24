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

"""Template rendering utilities.

Supported variables:
- {{account_id}}: Volcengine account ID (lazy-loaded)
- {{timestamp}}: current timestamp (YYYYMMDDHHMMSS)
- {{date}}: current date (YYYYMMDD)
- {{random_id}}: 8-hex random id

Example:
    >>> from agentkit.utils.template_utils import render_template
    >>> result = render_template("agentkit-platform-{{account_id}}")
"""

import re
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# In-memory cache for fetched account info
_ACCOUNT_CACHE: Dict[str, Any] = {}

# Precompiled pattern for template variables like {{var}}
P_VAR = re.compile(r"\{\{([^}]+)\}\}")


def _get_builtin_variables() -> Dict[str, str]:
    """Return builtin variables that do not require external calls."""
    import uuid

    now = datetime.now()

    variables = {
        "timestamp": now.strftime("%Y%m%d%H%M%S"),
        "date": now.strftime("%Y%m%d"),
        "random_id": uuid.uuid4().hex[:8],
    }

    return variables


def get_account_id() -> str:
    """Get Volcengine account ID with in-memory cache.

    Raises:
        ValueError: when account id cannot be retrieved
    """
    # Return from cache if available
    if "account_id" in _ACCOUNT_CACHE:
        logger.debug(f"Account ID from cache: {_ACCOUNT_CACHE['account_id']}")
        return _ACCOUNT_CACHE["account_id"]

    try:
        # Query STS API for caller identity
        from agentkit.toolkit.volcengine.sts import VeSTS

        logger.debug("Fetching account info via STS API...")
        sts = VeSTS()
        account_id = sts.get_account_id()

        if not account_id:
            raise ValueError("STS GetCallerIdentity returned empty account_id")

        account_id = str(account_id)

        # Cache result
        _ACCOUNT_CACHE["account_id"] = account_id
        logger.debug(f"Retrieved account_id: {account_id}")

        return account_id

    except Exception as e:
        # Build explicit error details
        error_type = type(e).__name__
        error_detail = str(e)
        error_msg = f"Failed to get account_id ({error_type}): {error_detail}"
        logger.error(error_msg)
        # Log full stack for debugging
        logger.debug("Full stack trace:", exc_info=True)
        raise ValueError(error_msg) from e


def clear_cache() -> None:
    """Clear cached account info (useful for tests or refreshing)."""
    global _ACCOUNT_CACHE
    _ACCOUNT_CACHE.clear()
    logger.debug("Account info cache cleared")


def render_template_safe(
    template_str: str,
    fallback: Optional[str] = None,
    extra_vars: Optional[Dict[str, str]] = None,
    sensitive: bool = False,
) -> str:
    """Render template safely, falling back to provided value on failure."""
    try:
        return render_template(template_str, extra_vars, sensitive=sensitive)
    except Exception as e:
        logger.warning(f"Template rendering failed, using fallback value: {e}")
        return fallback if fallback is not None else template_str


# NOTE: unified lazy-loading in render_template; removed unused _get_all_variables


# Optimized: fetch account_id only when needed
def render_template(
    template_str: str,
    extra_vars: Optional[Dict[str, str]] = None,
    sensitive: bool = False,
) -> str:
    """Render template string with builtin and optional variables.

    Lazily resolves account_id only when referenced.
    """
    # Fast-path: no placeholders
    if not template_str or "{{" not in template_str:
        if not sensitive:
            logger.debug("Skip rendering (no placeholders): %r", template_str)
        return template_str

    # Extract placeholders
    placeholders = [m.strip() for m in P_VAR.findall(template_str)]
    if not sensitive:
        logger.debug(
            "Render start: raw=%r, placeholders=%s", template_str, placeholders
        )

    needs_account_id = any(p.replace(" ", "") == "account_id" for p in placeholders)
    logger.debug("Needs account_id: %s", needs_account_id)

    # Build variables
    variables = _get_builtin_variables()

    # Fetch account_id only when needed
    if needs_account_id:
        try:
            account_id = get_account_id()
            if not account_id:
                raise ValueError("get_account_id() returned empty")
            variables["account_id"] = account_id
        except Exception as e:
            # Build full error with type and detail
            error_type = type(e).__name__
            error_detail = str(e)
            full_error = f"Failed to resolve account_id for template rendering ({error_type}): {error_detail}"
            logger.error(full_error)
            # Log full exception chain
            logger.debug("Full exception chain during rendering:", exc_info=True)
            raise ValueError(full_error) from e

    # Merge extra variables if provided
    if extra_vars:
        variables.update(extra_vars)

    # Render variables
    def replace_var(match):
        var_name = match.group(1).strip()
        if var_name in variables:
            return str(variables[var_name])
        else:
            logger.warning("Unknown template variable: %s", "{{%s}}" % var_name)
            return match.group(0)  # keep original token

    rendered = P_VAR.sub(replace_var, template_str)

    # Warn if unresolved placeholders remain
    unresolved = [m.strip() for m in P_VAR.findall(rendered)]
    if unresolved:
        logger.warning(
            "Unresolved placeholders after rendering: %s; rendered=%r",
            unresolved,
            rendered,
        )

    if not sensitive:
        logger.debug("Render done: %r -> %r", template_str, rendered)
    return rendered
