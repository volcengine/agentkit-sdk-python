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
    def invoke(self, config: Dict[str, Any], payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, stream: Optional[bool] = None) -> InvokeResult:
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
        timeout: int = 60
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
                logger.debug(f"{'Streaming' if stream else 'Normal'} invoke service: {endpoint}")
            
            # Use longer timeout for streaming calls
            actual_timeout = timeout if not stream else max(timeout, 300)
            
            response = requests.post(
                url=endpoint,
                json=payload,
                headers=headers,
                timeout=actual_timeout,
                stream=stream
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
                content_type = response.headers.get('Content-Type', '').lower()
                logger.debug(f"Content-Type: {content_type}")
                is_sse = 'text/event-stream' in content_type
                
                if is_sse:
                    logger.info(f"Detected SSE stream (Content-Type: {content_type})")
                    stream = True
                else:
                    logger.info(f"Detected non-stream response (Content-Type: {content_type})")
                    stream = False
            
            # Non-streaming call: return JSON response directly
            if not stream:
                try:
                    # Log response content for debugging
                    response_text = response.text
                    logger.info(f"Response text length: {len(response_text)}")
                    logger.info(f"Response text preview: {response_text[:200] if response_text else '(empty)'}")  
                    
                    # Double-check: if response starts with "data: ", it's actually SSE stream
                    if response_text.strip().startswith("data: "):
                        logger.warning("Response looks like SSE stream but Content-Type was not text/event-stream. Switching to stream mode.")
                        logger.warning(f"Using fallback stream parser - entire response ({len(response_text)} bytes) already loaded into memory. "
                                     f"For better performance, ensure server sets 'Content-Type: text/event-stream'.")
                        stream = True
                        # Need to re-process as streaming (note: response already fully loaded, loses real-time streaming benefit)
                        def event_generator_fallback():
                            """Parse SSE events from pre-read text"""
                            logger.debug(f"[FALLBACK] Starting generator, response_text length={len(response_text)}")
                            for i, line in enumerate(response_text.split('\n')):
                                line = line.strip()
                                if not line:
                                    continue
                                logger.debug(f"[FALLBACK] Line {i}: {line[:60]}...")
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()  # Remove "data: " prefix and trim
                                    if not data_str:
                                        continue
                                    try:
                                        event_data = json.loads(data_str)
                                        logger.debug(f"[FALLBACK] Parsed JSON successfully, type={type(event_data)}")
                                        yield event_data
                                    except json.JSONDecodeError as e:
                                        logger.warning(f"Failed to parse SSE data: {data_str[:100]}, error: {e}")
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
                                data_str = line[6:].strip()  # Remove "data: " prefix and trim
                                
                                if not data_str:
                                    # Empty data, skip
                                    continue
                                
                                try:
                                    event_data = json.loads(data_str)
                                    logger.debug("[STREAM] Yielding parsed dict")
                                    yield event_data
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse event data: {data_str[:100]}, error: {e}")
                                    # Skip unparseable lines, don't yield strings
                                    continue
                            else:
                                # Non-data lines, possibly comments or other SSE metadata, skip
                                if line.startswith(":"):
                                    # SSE comment line, skip
                                    logger.debug("[STREAM] Comment line, skipping")
                                    continue
                                elif line:
                                    logger.debug(f"[STREAM] Non-SSE line, skipping: {line[:80]}")
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
