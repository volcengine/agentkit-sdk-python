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

"""
Docker - 本地Docker工具集

容器管理、镜像管理、Dockerfile生成等本地开发工具
"""


# 使用延迟导入，避免在没有安装 docker 依赖时导入失败
def __getattr__(name):
    if name == "DockerManager":
        from .container import DockerManager

        return DockerManager
    elif name == "DockerfileRenderer":
        from .container import DockerfileRenderer

        return DockerfileRenderer
    elif name == "DockerfileManager":
        from .dockerfile import DockerfileManager

        return DockerfileManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DockerManager",
    "DockerfileRenderer",
    "DockerfileManager",
]
