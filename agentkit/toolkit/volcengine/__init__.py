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
Volcengine - Volcengine integration

CodePipeline, AgentKit Runtime, container image service, IAM authentication, etc.
"""


# Use lazy import to avoid dependency issues during import
def __getattr__(name):
    if name == "VeCodePipeline":
        from .code_pipeline import VeCodePipeline

        return VeCodePipeline
    elif name == "VeCR":
        from .cr import VeCR

        return VeCR
    elif name == "VeIAM":
        from .iam import VeIAM

        return VeIAM
    elif name == "CRService":
        from .services import CRService

        return CRService
    elif name == "CRServiceConfig":
        from .services import CRServiceConfig

        return CRServiceConfig
    elif name == "TOSService":
        from .services import TOSService

        return TOSService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "VeCodePipeline",
    "VeCR",
    "VeIAM",
    "CRService",
    "CRServiceConfig",
    "TOSService",
]
