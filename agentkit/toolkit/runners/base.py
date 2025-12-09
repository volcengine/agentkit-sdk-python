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

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, Generator, Tuple
import logging
import requests
import json
from urllib.parse import urljoin
from dataclasses import dataclass

from agentkit.toolkit.models import DeployResult, StatusResult, InvokeResult
from agentkit.toolkit.reporter import Reporter, SilentReporter

logger = logging.getLogger(__name__)


class Runner(ABC):
    """
    Abstract base class for service runners.

    Responsibilities:
    - Execute pre-built images (locally or in cloud)
    - Provide deployment, invocation, and status query interfaces
    - Manage runtime resources (containers/Runtimes)

    Design notes:
        Runner does not require project_dir since it only manages execution
        of pre-built images. All necessary information is passed via config objects.
    """

    def __init__(self, reporter: Optional[Reporter] = None):
        """
        Initialize Runner.

        Args:
            reporter: Progress reporter for deployment and runtime status updates

        Note:
            Runner does not require project_dir since it only manages execution.
            Project directory information should be passed via config objects if needed.
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.reporter = reporter or SilentReporter()

    # ===== Configuration types =====
    @dataclass
    class TimeoutPolicy:
        detect_timeout: int = 2
        list_apps_timeout: int = 3
        session_timeout: int = 5
        invoke_timeout: int = 300
        sse_timeout: int = 600

    @dataclass
    class InvokeContext:
        base_endpoint: str
        invoke_endpoint: str
        headers: Dict[str, str]
        is_a2a: bool
        preferred_app_name: Optional[str] = None

    @abstractmethod
    def deploy(self, config: Dict[str, Any]) -> DeployResult:
        """Execute deployment.

        Args:
            config: Deployment configuration

        Returns:
            DeployResult: Unified deployment result object
        """
        pass

    @abstractmethod
    def destroy(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def status(self, config: Dict[str, Any]) -> StatusResult:
        """Query service status.

        Args:
            config: Configuration information

        Returns:
            StatusResult: Unified status result object
        """
        pass

    @abstractmethod
    def invoke(
        self,
        config: Dict[str, Any],
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """Invoke service.

        Args:
            config: Configuration information
            payload: Request payload
            headers: Request headers
            stream: Stream mode. None=auto-detect (default), True=force streaming, False=force non-streaming

        Returns:
            InvokeResult: Unified invocation result object

        Note:
            InvokeResult.response can be dict (non-streaming) or generator (streaming)
            InvokeResult.is_streaming indicates response type
        """
        pass

    def _http_post_invoke(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        stream: Optional[bool] = None,
        timeout: int = 60,
    ) -> Union[Tuple[bool, Any], Tuple[bool, Generator[Dict[str, Any], None, None]]]:
        """Generic HTTP POST invocation method supporting streaming and non-streaming with auto-detection.

        Args:
            endpoint: Invocation endpoint URL
            payload: Request payload
            headers: Request headers
            stream: Stream mode. None=auto-detect, True=force streaming, False=force non-streaming
            timeout: Timeout in seconds. Longer timeout recommended for streaming

        Returns:
            If stream=False: (success_flag, response_dict)
            If stream=True: (success_flag, generator_object)
        """
        try:
            # Auto-detect mode: attempt to establish connection first
            auto_detect = stream is None
            if auto_detect:
                logger.debug(f"Auto-detecting stream support for: {endpoint}")
                # Default to streaming first
                stream = True
            else:
                logger.debug(
                    f"{'Streaming' if stream else 'Normal'} invoke service: {endpoint}"
                )

            # Use longer timeout for streaming calls
            actual_timeout = timeout if not stream else max(timeout, 300)
            response = requests.post(
                url=endpoint,
                json=payload,
                headers=headers,
                timeout=actual_timeout,
                stream=stream,
            )

            if response.status_code != 200:
                error_msg = f"Invocation failed: {response.status_code} {response.text}"
                logger.error(error_msg)
                return False, error_msg

            # Log response information
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Auto-detect: determine based on Content-Type
            if auto_detect:
                content_type = response.headers.get("Content-Type", "").lower()
                logger.debug(f"Content-Type: {content_type}")
                is_sse = "text/event-stream" in content_type

                if is_sse:
                    logger.info(f"Detected SSE stream (Content-Type: {content_type})")
                    stream = True
                else:
                    logger.info(
                        f"Detected non-stream response (Content-Type: {content_type})"
                    )
                    stream = False

            # Non-streaming call: return JSON response directly
            if not stream:
                try:
                    # Log response content for debugging
                    response_text = response.text
                    logger.info(f"Response text length: {len(response_text)}")
                    logger.info(
                        f"Response text preview: {response_text[:200] if response_text else '(empty)'}"
                    )

                    # Double-check: if response starts with "data: ", it's actually SSE stream
                    if response_text.strip().startswith("data: "):
                        logger.warning(
                            "Response looks like SSE stream but Content-Type was not text/event-stream. Switching to stream mode."
                        )
                        logger.warning(
                            f"Using fallback stream parser - entire response ({len(response_text)} bytes) already loaded into memory. "
                            f"For better performance, ensure server sets 'Content-Type: text/event-stream'."
                        )
                        stream = True

                        # Need to re-process as streaming (note: response already fully loaded, loses real-time streaming benefit)
                        def event_generator_fallback():
                            """Parse SSE events from pre-read text"""
                            logger.debug(
                                f"[FALLBACK] Starting generator, response_text length={len(response_text)}"
                            )
                            for i, line in enumerate(response_text.split("\n")):
                                line = line.strip()
                                if not line:
                                    continue
                                logger.debug(f"[FALLBACK] Line {i}: {line[:60]}...")
                                if line.startswith("data: "):
                                    data_str = line[
                                        6:
                                    ].strip()  # Remove "data: " prefix and trim
                                    if not data_str:
                                        continue
                                    try:
                                        event_data = json.loads(data_str)
                                        logger.debug(
                                            f"[FALLBACK] Parsed JSON successfully, type={type(event_data)}"
                                        )
                                        yield event_data
                                    except json.JSONDecodeError as e:
                                        logger.warning(
                                            f"Failed to parse SSE data: {data_str[:100]}, error: {e}"
                                        )
                                        # Skip unparseable lines
                                        continue

                        return True, event_generator_fallback()

                    # Normal JSON response
                    response_data = response.json()
                    logger.info("Successfully parsed JSON response")
                    return True, response_data
                except ValueError as e:
                    error_msg = f"Response parsing failed: {str(e)}"
                    logger.error(error_msg)
                    logger.error(f"Response content: {response.text[:500]}")
                    return False, error_msg

            # Streaming call: return generator
            else:

                def event_generator():
                    """Generator function: parse SSE format streaming response line by line"""
                    try:
                        for line in response.iter_lines(decode_unicode=True):
                            if not line:
                                continue

                            line = line.strip()
                            logger.debug(f"[STREAM] Raw line: {line[:80]}")

                            # SSE format: "data: {json}\n\n"
                            if line.startswith("data: "):
                                data_str = line[
                                    6:
                                ].strip()  # Remove "data: " prefix and trim

                                if not data_str:
                                    # Empty data, skip
                                    continue

                                try:
                                    event_data = json.loads(data_str)
                                    logger.debug("[STREAM] Yielding parsed dict")
                                    yield event_data
                                except json.JSONDecodeError as e:
                                    logger.warning(
                                        f"Failed to parse event data: {data_str[:100]}, error: {e}"
                                    )
                                    # Skip unparseable lines, don't yield strings
                                    continue
                            else:
                                # Non-data lines, possibly comments or other SSE metadata, skip
                                if line.startswith(":"):
                                    # SSE comment line, skip
                                    logger.debug("[STREAM] Comment line, skipping")
                                    continue
                                elif line:
                                    logger.debug(
                                        f"[STREAM] Non-SSE line, skipping: {line[:80]}"
                                    )
                                    continue
                    except Exception as e:
                        logger.error(f"Error in stream processing: {str(e)}")
                        yield {"error": str(e)}

                return True, event_generator()

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {actual_timeout} seconds"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Invocation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    # ===== Shared helpers for ADK compatibility =====
    def _detect_adk_backend(
        self, base_endpoint: str, headers: Dict[str, str], timeout_s: int = 2
    ) -> bool:
        """Lightweight detection of ADK webserver by probing /list-apps.

        Returns True if response looks like ADK (list or dict with 'apps').
        """
        try:
            resp = requests.get(
                urljoin(base_endpoint, "list-apps"), headers=headers, timeout=timeout_s
            )
            if resp.status_code != 200:
                return False
            try:
                data = resp.json()
            except Exception:
                return False
            return self._is_adk_list_apps_response(data)
        except Exception:
            return False

    def _is_adk_list_apps_response(self, data: Any) -> bool:
        if isinstance(data, list):
            return True
        if isinstance(data, dict) and ("apps" in data):
            return True
        return False

    def _build_adk_run_sse_payload(
        self, app_name: str, headers: Dict[str, str], original_payload: Any
    ) -> Dict[str, Any]:
        """Construct ADK RunAgentRequest payload in camelCase."""
        user_id = headers.get("user_id") or headers.get("x-user-id") or "agentkit_user"
        session_id = (
            headers.get("session_id")
            or headers.get("x-session-id")
            or "agentkit_sample_session"
        )
        text = None
        if isinstance(original_payload, dict):
            val = original_payload.get("prompt")
            if isinstance(val, str):
                text = val
        if text is None:
            try:
                text = json.dumps(original_payload, ensure_ascii=False)
            except Exception:
                text = ""
        req: Dict[str, Any] = {
            "appName": app_name,
            "userId": user_id,
            "sessionId": session_id,
            "newMessage": {"role": "user", "parts": [{"text": text or ""}]},
            "streaming": True,
        }
        if isinstance(original_payload, dict) and "state_delta" in original_payload:
            req["stateDelta"] = original_payload.get("state_delta")
        return req

    def _should_fallback_to_adk(self, err_str: str) -> bool:
        """Return True if error string indicates /invoke not found (404/405)."""
        err = err_str or ""
        return (
            (" 404 " in err)
            or err.startswith("Invocation failed: 404")
            or (" 405 " in err)
            or err.startswith("Invocation failed: 405")
        )

    def _post_run_sse(
        self,
        base_endpoint: str,
        headers: Dict[str, str],
        adk_payload: Dict[str, Any],
        timeout_s: int = 300,
    ) -> Union[Tuple[bool, Any], Tuple[bool, Generator[Dict[str, Any], None, None]]]:
        return self._http_post_invoke(
            endpoint=urljoin(base_endpoint, "run_sse"),
            payload=adk_payload,
            headers=headers,
            stream=True,
            timeout=timeout_s,
        )

    # ===== Unified ADK-compatible invocation flow =====
    def _is_a2a(self, common_config: Any) -> bool:
        val = None
        if common_config:
            val = getattr(common_config, "agent_type", None) or getattr(
                common_config, "template_type", None
            )
        val = val or ""
        try:
            return "a2a" in str(val).lower()
        except Exception:
            return False

    def _invoke_with_adk_compat(
        self,
        ctx: "Runner.InvokeContext",
        payload: Any,
        policy: "Runner.TimeoutPolicy",
    ) -> Tuple[bool, Any, bool]:
        """Unified invoke flow with ADK detection and fallback.

        Returns: (success, response_data, is_streaming)
        """
        # A2A: invoke directly using root or provided endpoint
        if ctx.is_a2a:
            success, response_data = self._http_post_invoke(
                endpoint=ctx.invoke_endpoint,
                payload=payload,
                headers=ctx.headers,
                stream=None,
                timeout=policy.invoke_timeout,
            )
        else:
            # Non-A2A: detect ADK first
            if self._detect_adk_backend(
                ctx.base_endpoint, ctx.headers, timeout_s=policy.detect_timeout
            ):
                app_name = self._get_adk_app_name(
                    ctx.base_endpoint,
                    ctx.headers,
                    preferred_name=ctx.preferred_app_name,
                    timeout_s=policy.list_apps_timeout,
                )
                app_name = app_name or "agentkit-app"
                user_id = (
                    ctx.headers.get("user_id")
                    or ctx.headers.get("x-user-id")
                    or "agentkit_user"
                )
                session_id = (
                    ctx.headers.get("session_id")
                    or ctx.headers.get("x-session-id")
                    or "agentkit_sample_session"
                )
                self._ensure_adk_session(
                    ctx.base_endpoint,
                    ctx.headers,
                    app_name,
                    user_id,
                    session_id,
                    timeout_s=policy.session_timeout,
                )
                adk_payload = self._build_adk_run_sse_payload(
                    app_name, ctx.headers, payload
                )
                success, response_data = self._post_run_sse(
                    ctx.base_endpoint,
                    ctx.headers,
                    adk_payload,
                    timeout_s=policy.sse_timeout,
                )
            else:
                success, response_data = self._http_post_invoke(
                    endpoint=ctx.invoke_endpoint,
                    payload=payload,
                    headers=ctx.headers,
                    stream=None,
                    timeout=policy.invoke_timeout,
                )
                if not success and self._should_fallback_to_adk(str(response_data)):
                    app_name = self._get_adk_app_name(
                        ctx.base_endpoint,
                        ctx.headers,
                        preferred_name=ctx.preferred_app_name,
                        timeout_s=policy.list_apps_timeout,
                    )
                    app_name = app_name or "agentkit-app"
                    user_id = (
                        ctx.headers.get("user_id")
                        or ctx.headers.get("x-user-id")
                        or "agentkit_user"
                    )
                    session_id = (
                        ctx.headers.get("session_id")
                        or ctx.headers.get("x-session-id")
                        or "agentkit_sample_session"
                    )
                    self._ensure_adk_session(
                        ctx.base_endpoint,
                        ctx.headers,
                        app_name,
                        user_id,
                        session_id,
                        timeout_s=policy.session_timeout,
                    )
                    adk_payload = self._build_adk_run_sse_payload(
                        app_name, ctx.headers, payload
                    )
                    success, response_data = self._post_run_sse(
                        ctx.base_endpoint,
                        ctx.headers,
                        adk_payload,
                        timeout_s=policy.sse_timeout,
                    )

        is_streaming = hasattr(response_data, "__iter__") and not isinstance(
            response_data, (dict, str, list, bytes)
        )
        return success, response_data, is_streaming

    def _get_adk_app_name(
        self,
        base_endpoint: str,
        headers: Dict[str, str],
        preferred_name: Optional[str] = None,
        timeout_s: int = 3,
    ) -> Optional[str]:
        """Fetch app name from ADK list-apps endpoint.

        Tries detailed mode first to get structured names; falls back to simple list.
        If preferred_name is provided and exists in server response, selects it; otherwise select the first.
        Returns None if no apps are available.
        """
        try:
            # Try detailed listing
            resp = requests.get(
                urljoin(base_endpoint, "list-apps?detailed=true"),
                headers=headers,
                timeout=timeout_s,
            )
            names: list[str] = []
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and isinstance(data.get("apps"), list):
                        for item in data["apps"]:
                            name = item.get("name") if isinstance(item, dict) else None
                            if isinstance(name, str):
                                names.append(name)
                except Exception:
                    pass
            # Fallback to simple list
            if not names:
                resp2 = requests.get(
                    urljoin(base_endpoint, "list-apps"),
                    headers=headers,
                    timeout=timeout_s,
                )
                if resp2.status_code == 200:
                    try:
                        data2 = resp2.json()
                        if isinstance(data2, list):
                            for item in data2:
                                if isinstance(item, str):
                                    names.append(item)
                    except Exception:
                        pass
            if not names:
                return None
            # Prefer a matching name if provided
            if preferred_name and preferred_name in names:
                return preferred_name
            return names[0]
        except Exception:
            return None

    def _ensure_adk_session(
        self,
        base_endpoint: str,
        headers: Dict[str, str],
        app_name: str,
        user_id: str,
        session_id: str,
        timeout_s: int = 5,
    ) -> bool:
        """Ensure the ADK session exists; create it if missing.

        Returns True on success; False if creation/check fails.
        """
        try:
            get_url = urljoin(
                base_endpoint,
                f"apps/{app_name}/users/{user_id}/sessions/{session_id}",
            )
            resp = requests.get(get_url, headers=headers, timeout=timeout_s)
            if resp.status_code == 200:
                return True
            if resp.status_code != 404:
                # Other errors
                self.logger.warning(
                    f"Session check failed: {resp.status_code} {resp.text[:200]}"
                )
                return False
            # Create session
            create_url = urljoin(
                base_endpoint, f"apps/{app_name}/users/{user_id}/sessions"
            )
            payload = {"sessionId": session_id}
            resp2 = requests.post(
                create_url,
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
                timeout=timeout_s,
            )
            if resp2.status_code == 200:
                return True
            self.logger.error(
                f"Session creation failed: {resp2.status_code} {resp2.text[:200]}"
            )
            return False
        except Exception as e:
            self.logger.exception(f"Ensure session error: {e}")
            return False
