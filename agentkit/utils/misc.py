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

import math
import string
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def generate_random_id(length=8):
    """generate a random id

    Args:
        length: the length of the random id

    Returns:
        the random id string
    """
    # define the character set: lowercase letters + digits
    characters = string.ascii_lowercase + string.digits
    random_id = "".join(random.choice(characters) for _ in range(length))
    return random_id


def generate_runtime_name(agent_name: str) -> str:
    """生成Runtime名称

    Args:
        agent_name: Agent名称

    Returns:
        格式为 "{agent_name}-{random_id}" 的Runtime名称
    """
    return f"{agent_name}-{generate_random_id()}"


def generate_runtime_role_name() -> str:
    """生成Runtime角色名称

    Returns:
        格式为 "AgentKit-Runtime-Default-ServiceRole-{random_id}" 的角色名称
    """
    return f"AgentKit-Runtime-Default-ServiceRole-{generate_random_id(7)}"


def generate_apikey_name() -> str:
    """生成API密钥名称

    Returns:
        格式为 "API-KEY-{random_id}" 的API密钥名称
    """
    return f"API-KEY-{generate_random_id()}"


def generate_client_token() -> str:
    """生成Client Token

    Returns:
        16位随机字符串
    """
    return generate_random_id(16)


def calculate_nonlinear_progress(
    elapsed: float,
    max_time: float,
    expected_time: float = 30.0,
    max_ratio: float = 0.95,
) -> float:
    """Calculate non-linear progress using exponential decay curve.

    This creates a progress bar that advances quickly at first, then slows down
    as it approaches completion. Useful for tasks with unpredictable duration.

    Formula: progress = max_time * (1 - e^(-elapsed/expected_time))

    Example progress at different times (with expected_time=30):
        - At 30s:  ~63%
        - At 60s:  ~86%
        - At 90s:  ~95%

    Args:
        elapsed: Elapsed time in seconds.
        max_time: Maximum time (used as progress bar total).
        expected_time: Expected completion time, controls curve speed.
            Smaller = faster initial progress.
        max_ratio: Maximum progress ratio before task completes (default 0.95).
            Prevents reaching 100% until task actually finishes.

    Returns:
        Progress value between 0 and max_time * max_ratio.
    """
    progress = max_time * (1 - math.exp(-elapsed / expected_time))
    return min(progress, max_time * max_ratio)


def retry(
    func: Callable[[], T],
    retries: int = 3,
    delay: float = 1.0,
) -> T:
    for attempt in range(retries):
        try:
            return func()
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(delay)
