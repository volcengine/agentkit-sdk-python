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

import os
import tarfile
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ArchiveConfig:
    """打包配置"""

    source_dir: str = field(default=".", metadata={"description": "源目录"})
    output_dir: str = field(default="/tmp", metadata={"description": "输出目录"})
    archive_name: str = field(default="project", metadata={"description": "压缩包名称"})

    # 排除配置
    exclude_patterns: List[str] = field(
        default_factory=lambda: [
            "__pycache__",
            "agentkit.yaml",
            ".env",
            "*.pyc",
            "*.pyo",
            ".git",
            ".gitignore",
            ".DS_Store",
            "*.log",
            "tmp/",
            "dist/",
            "build/",
            "*.egg-info/",
            ".agentkit/",
        ]
    )

    include_patterns: List[str] = field(
        default_factory=lambda: [
            "*.py",
            "*.go",
            "*.mod",
            "*.sum",
            "*.sh",
            "*.txt",
            "*.md",
            "*.json",
            "*.yaml",
            "*.yml",
            "Dockerfile*",
            "requirements*",
            "setup.py",
            "pyproject.toml",
        ]
    )


class ProjectArchiver:
    """项目打包工具"""

    def __init__(self, config: ArchiveConfig):
        """初始化打包工具

        Args:
            config: 打包配置
        """
        self.config = config
        self.source_path = Path(config.source_dir).resolve()
        self.output_path = Path(config.output_dir).resolve()

    def create_archive(self) -> str:
        """创建项目压缩包

        Returns:
            压缩包完整路径
        """
        try:
            logger.info(f"开始打包项目: {self.source_path}")

            # 确保输出目录存在
            self.output_path.mkdir(parents=True, exist_ok=True)

            # 生成压缩包路径
            archive_path = self.output_path / f"{self.config.archive_name}.tar.gz"

            # 获取要打包的文件列表
            files_to_include = self._get_files_to_include()

            if not files_to_include:
                raise ValueError("没有找到需要打包的文件")

            # 创建压缩包
            with tarfile.open(archive_path, "w:gz") as tar:
                for file_path in files_to_include:
                    arcname = file_path.relative_to(self.source_path)
                    tar.add(file_path, arcname=arcname)
                    logger.debug(f"添加文件: {arcname}")

            logger.info(f"打包完成: {archive_path}")
            return str(archive_path)

        except Exception as e:
            logger.error(f"打包失败: {str(e)}")
            raise

    def _get_files_to_include(self) -> List[Path]:
        """获取需要打包的文件列表

        Returns:
            文件路径列表
        """
        files_to_include = []

        try:
            # 遍历源目录
            for root, dirs, files in os.walk(self.source_path):
                root_path = Path(root)

                # 检查是否需要跳过当前目录
                if self._should_skip_directory(root_path):
                    dirs[:] = []  # 跳过子目录
                    continue

                # 处理文件
                for file_name in files:
                    file_path = root_path / file_name

                    if self._should_include_file(file_path):
                        files_to_include.append(file_path)

            return files_to_include

        except Exception as e:
            logger.error(f"获取文件列表失败: {str(e)}")
            raise

    def _should_skip_directory(self, dir_path: Path) -> bool:
        """检查是否应该跳过目录

        Args:
            dir_path: 目录路径

        Returns:
            是否应该跳过
        """
        try:
            # 检查排除模式 - 使用通配符匹配
            for pattern in self.config.exclude_patterns:
                if pattern.endswith("/"):
                    # 目录模式匹配
                    dir_pattern = pattern.rstrip("/")
                    if self._match_pattern(
                        dir_path.name, dir_pattern
                    ) or self._match_pattern(str(dir_path), dir_pattern):
                        return True
                else:
                    # 也检查目录名是否匹配文件模式
                    if self._match_pattern(dir_path.name, pattern):
                        return True

            # 检查隐藏目录
            if dir_path.name.startswith(".") and dir_path.name != ".":
                return True

            return False

        except Exception:
            return False

    def _should_include_file(self, file_path: Path) -> bool:
        """检查是否应该包含文件

        Args:
            file_path: 文件路径

        Returns:
            是否应该包含
        """
        try:
            # 检查排除模式
            for pattern in self.config.exclude_patterns:
                if not pattern.endswith("/"):
                    if self._match_pattern(
                        file_path.name, pattern
                    ) or self._match_pattern(str(file_path), pattern):
                        return False

            # 检查包含模式
            for pattern in self.config.include_patterns:
                if self._match_pattern(file_path.name, pattern) or self._match_pattern(
                    str(file_path), pattern
                ):
                    return True

            return False

        except Exception:
            return False

    def _match_pattern(self, text: str, pattern: str) -> bool:
        """检查文本是否匹配模式（支持通配符）

        Args:
            text: 要匹配的文本
            pattern: 模式（支持*通配符）

        Returns:
            是否匹配
        """
        import fnmatch

        return fnmatch.fnmatch(text, pattern)

    def get_project_info(self) -> dict:
        """获取项目信息

        Returns:
            项目信息字典
        """
        try:
            files = self._get_files_to_include()

            info = {
                "source_dir": str(self.source_path),
                "total_files": len(files),
                "total_size": sum(f.stat().st_size for f in files),
                "files": [str(f.relative_to(self.source_path)) for f in files],
            }

            return info

        except Exception as e:
            logger.error(f"获取项目信息失败: {str(e)}")
            return {}


def create_project_archive(
    source_dir: str = ".",
    output_dir: str = "/tmp",
    archive_name: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
) -> str:
    """快速创建项目压缩包

    Args:
        source_dir: 源目录
        output_dir: 输出目录
        archive_name: 压缩包名称（默认为项目目录名）
        exclude_patterns: 排除模式列表
        include_patterns: 包含模式列表

    Returns:
        压缩包完整路径
    """
    try:
        source_path = Path(source_dir).resolve()

        if not archive_name:
            archive_name = source_path.name

        config = ArchiveConfig(
            source_dir=source_dir, output_dir=output_dir, archive_name=archive_name
        )

        if exclude_patterns:
            config.exclude_patterns = exclude_patterns

        if include_patterns:
            config.include_patterns = include_patterns

        archiver = ProjectArchiver(config)
        return archiver.create_archive()

    except Exception as e:
        logger.error(f"创建压缩包失败: {str(e)}")
        raise
