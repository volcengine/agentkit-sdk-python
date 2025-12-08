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

"""Dockerfile 智能管理器"""

import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Callable, Dict, Any

from .metadata import DockerfileDecision, MetadataExtractor, ContentComparator
from agentkit.toolkit.context import ExecutionContext

logger = logging.getLogger(__name__)


class DockerfileManager:
    """
    Dockerfile 智能管理器

    负责决策是否需要重新生成 Dockerfile，并管理生成过程。
    支持 LocalDockerBuilder 和 VeCPCRBuilder。
    """

    def __init__(self, workdir: Path, custom_logger: Optional[logging.Logger] = None):
        """
        初始化管理器

        Args:
            workdir: 工作目录
            custom_logger: 自定义日志器

        Note:
            输出信息通过 ExecutionContext 的 Reporter 进行，
            CLI 会自动设置 ConsoleReporter，SDK 会设置 SilentReporter
        """
        self.workdir = workdir
        self.dockerfile_path = workdir / "Dockerfile"
        self.logger = custom_logger or logger

    def prepare_dockerfile(
        self,
        config_hash_dict: Dict[str, Any],
        content_generator: Callable[[], str],
        force_regenerate: bool = False,
    ) -> Tuple[bool, str]:
        """
        准备 Dockerfile（决策 + 生成）

        Args:
            config_hash_dict: 用于计算配置哈希的字典
            content_generator: 内容生成函数（返回不含元数据头的 Dockerfile 内容）
            force_regenerate: 强制重新生成

        Returns:
            (是否生成了新文件, Dockerfile路径)
        """
        # 1. 决策是否需要生成
        decision, reason = self._should_regenerate(
            config_hash_dict, content_generator, force_regenerate
        )

        should_gen = decision in (
            DockerfileDecision.GENERATE_NEW,
            DockerfileDecision.GENERATE_CONFIG_CHANGED,
        )

        # 2. 如果需要生成
        if should_gen:
            self.logger.info(f"生成 Dockerfile: {reason}")

            # 用户友好的提示信息
            self._print_user_message(
                "📝 Generating Dockerfile...", f"Reason: {reason}", style="cyan"
            )

            # 创建备份（如果存在）
            if self.dockerfile_path.exists():
                backup_path = self._create_backup()
                if backup_path:
                    self.logger.info(f"已备份到: {backup_path}")
                    # 显示相对于工作目录的路径
                    relative_path = backup_path.relative_to(self.workdir)
                    self._print_user_message(
                        f"💾 Backup created: {relative_path}", style="yellow"
                    )

            # 生成内容
            try:
                dockerfile_content = content_generator()
            except Exception as e:
                self.logger.error(f"生成 Dockerfile 内容失败: {e}", exc_info=True)
                raise

            # 添加元数据头
            full_content = self._add_metadata_header(
                dockerfile_content, config_hash_dict
            )

            # 写入文件
            try:
                self.dockerfile_path.write_text(full_content, encoding="utf-8")
                self.logger.info(f"Dockerfile 已生成: {self.dockerfile_path}")

                # 成功提示
                if decision == DockerfileDecision.GENERATE_CONFIG_CHANGED:
                    # 配置变化导致的更新
                    self._print_user_message(
                        "Dockerfile updated",
                        "Note: Dockerfile auto-updates when config changes. Remove header to fully customize.",
                        style="green",
                    )
                else:
                    # 首次生成
                    self._print_user_message(
                        "Dockerfile generated",
                        "Note: Dockerfile auto-updates when config changes. Remove header to fully customize.",
                        style="green",
                    )

            except Exception as e:
                self.logger.error(f"写入 Dockerfile 失败: {e}", exc_info=True)
                raise

            return True, str(self.dockerfile_path)

        # 3. 使用现有文件
        else:
            self.logger.info(f"使用现有 Dockerfile: {reason}")

            # 用户友好的提示信息（基于枚举决策）
            if decision == DockerfileDecision.KEEP_CONFIG_CONFLICT:
                # 配置变化 + 用户修改 → 显著警告
                self._print_user_message(
                    "⚠️  Using existing Dockerfile (potential risk)",
                    "Detected: Config updated + Dockerfile modified by user",
                    "Using your custom version, but it may be incompatible with new config!",
                    "Suggested actions:",
                    "  1. Check if Dockerfile needs updates for new config",
                    "  2. Or use --regenerate-dockerfile to regenerate",
                    style="yellow",
                )
            elif decision == DockerfileDecision.KEEP_USER_MODIFIED:
                self._print_user_message(
                    "🔒 Using existing Dockerfile",
                    "Detected user customization, keeping current version",
                    "Tip: Use --regenerate-dockerfile to regenerate if needed",
                    style="blue",
                )
            elif decision == DockerfileDecision.KEEP_USER_CUSTOM:
                self._print_user_message(
                    "📄 Using existing Dockerfile",
                    "Custom Dockerfile detected (no tool header), keeping as-is",
                    style="blue",
                )
            elif decision == DockerfileDecision.KEEP_UP_TO_DATE:
                self._print_user_message(
                    "✓ Using existing Dockerfile",
                    "Current file is up-to-date",
                    style="dim",
                )
            else:
                # 包括 KEEP_ERROR
                self._print_user_message(
                    "📄 Using existing Dockerfile", f"{reason}", style="blue"
                )

            return False, str(self.dockerfile_path)

    def _should_regenerate(
        self,
        config_hash_dict: Dict[str, Any],
        content_generator: Callable[[], str],
        force: bool,
    ) -> Tuple[DockerfileDecision, str]:
        """
        决策是否需要重新生成 Dockerfile

        Args:
            config_hash_dict: 配置哈希字典
            content_generator: 内容生成函数
            force: 强制重新生成

        Returns:
            (决策枚举, 原因描述)
        """
        # 1. 强制重新生成
        if force:
            return DockerfileDecision.GENERATE_CONFIG_CHANGED, "Force regenerate"

        # 2. 文件不存在
        if not self.dockerfile_path.exists():
            return DockerfileDecision.GENERATE_NEW, "Dockerfile does not exist"

        # 3. 读取现有文件
        content = self._read_safely()
        if content is None:
            return (
                DockerfileDecision.GENERATE_NEW,
                "Cannot read existing file, regenerating",
            )

        # 4. 提取元数据
        metadata = MetadataExtractor.extract(content)

        # 5. 不是工具管理的文件（用户文件）
        if not metadata.is_managed:
            return DockerfileDecision.KEEP_USER_CUSTOM, "Custom Dockerfile detected"

        # 6. 计算当前配置哈希
        current_hash = MetadataExtractor.calculate_config_hash(config_hash_dict)

        # 7. 检查内容是否被用户修改（通过 content_hash）
        current_content_hash = MetadataExtractor.calculate_content_hash(content)

        # 如果没有记录的 content_hash（旧版本文件），使用内容比较
        if not metadata.content_hash:
            self.logger.debug("旧版本文件无 content_hash，使用内容比较...")
            try:
                expected_content = content_generator()
                expected_full = self._add_metadata_header(
                    expected_content, config_hash_dict
                )
                is_modified = ContentComparator.is_modified(content, expected_full)
            except Exception as e:
                self.logger.warning(f"内容比较失败: {e}")
                is_modified = False  # 保守策略
        else:
            # 通过 content_hash 比较
            is_modified = current_content_hash != metadata.content_hash
            if is_modified:
                self.logger.info(
                    f"内容已修改: {metadata.content_hash} -> {current_content_hash}"
                )

        # 8. 根据配置变化和内容修改情况决策
        config_changed = metadata.config_hash != current_hash

        if not config_changed and not is_modified:
            # 配置未变 + 内容未改 → 已是最新
            return DockerfileDecision.KEEP_UP_TO_DATE, "Dockerfile is up-to-date"

        elif not config_changed and is_modified:
            # 配置未变 + 内容已改 → 保留用户版本
            self.logger.info("Dockerfile 内容已被用户修改")
            return DockerfileDecision.KEEP_USER_MODIFIED, "Dockerfile modified by user"

        elif config_changed and not is_modified:
            # 配置已变 + 内容未改 → 更新
            self.logger.info("配置已变化，Dockerfile 未被用户修改，将更新")
            return (
                DockerfileDecision.GENERATE_CONFIG_CHANGED,
                "Config updated, regenerating Dockerfile",
            )

        else:
            # 配置已变 + 内容已改 → 保留用户版本但警告
            self.logger.warning("配置已变化，且 Dockerfile 已被用户修改，保留用户版本")
            return (
                DockerfileDecision.KEEP_CONFIG_CONFLICT,
                "Config changed + Dockerfile modified (potential conflict)",
            )

    def _add_metadata_header(
        self,
        content: str,
        config_hash_dict: Dict[str, Any],
        override_hash: Optional[str] = None,
    ) -> str:
        """
        添加元数据头部

        Args:
            content: Dockerfile 主体内容
            config_hash_dict: 配置哈希字典
            override_hash: 覆盖计算的哈希（用于对比）

        Returns:
            带元数据头的完整内容
        """
        try:
            # 尝试导入版本号
            try:
                from agentkit.version import VERSION

                version = VERSION
            except ImportError as e:
                self.logger.warning(f"can not import version: {e}, use unknown")
                version = "unknown"

            # 计算或使用指定的配置哈希
            if override_hash:
                config_hash = override_hash
            else:
                config_hash = MetadataExtractor.calculate_config_hash(config_hash_dict)

            timestamp = datetime.now().isoformat()

            # 计算内容哈希
            content_hash = MetadataExtractor.calculate_content_hash(content)

            header = f"""# ============================================================================
# AUTO-GENERATED by AgentKit v{version}
# ============================================================================
# Source: agentkit.yaml
# Checksum: sha256:{config_hash}
# ContentHash: sha256:{content_hash}
# Generated: {timestamp}
# 
# This file is automatically generated and managed by AgentKit:
#   - It will be auto-updated when agentkit.yaml config changes (old version backed up)
#   - To fully customize, remove this header comment
#   - After removing the header, AgentKit will no longer manage this file
# 
# Force regenerate command:
#   agentkit build --regenerate-dockerfile
# 
# ============================================================================

"""
            return header + content

        except Exception as e:
            self.logger.error(f"添加元数据头失败: {e}", exc_info=True)
            # 降级：返回原内容
            return content

    def _read_safely(self) -> Optional[str]:
        """
        安全读取 Dockerfile

        Returns:
            文件内容，失败返回 None
        """
        if not self.dockerfile_path.exists():
            return None

        # 检查文件大小
        try:
            file_size = self.dockerfile_path.stat().st_size

            # 空文件
            if file_size == 0:
                self.logger.warning("Dockerfile 为空文件")
                return None

            # 文件过大（不太可能是 Dockerfile）
            if file_size > 1024 * 1024:  # 1MB
                self.logger.warning("Dockerfile 文件过大，可能不是标准文件")
                return None

        except Exception as e:
            self.logger.error(f"检查文件大小失败: {e}")
            return None

        # 尝试多种编码读取
        encodings = ["utf-8", "utf-8-sig", "latin-1"]
        for encoding in encodings:
            try:
                content = self.dockerfile_path.read_text(encoding=encoding)
                return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"读取 Dockerfile 失败 ({encoding}): {e}")
                return None

        self.logger.error("无法解码 Dockerfile（尝试了多种编码）")
        return None

    def _create_backup(self) -> Optional[Path]:
        """
        创建备份（保存在隐藏文件夹中）

        Returns:
            备份文件路径，失败返回 None
        """
        if not self.dockerfile_path.exists():
            return None

        # 创建隐藏的备份目录
        backup_dir = self.workdir / ".agentkit" / "dockerfile_backups"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"创建备份目录失败: {e}，将继续生成")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"Dockerfile.backup.{timestamp}"

        try:
            shutil.copy2(self.dockerfile_path, backup_path)
            self.logger.info(f"备份创建成功: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.warning(f"创建备份失败: {e}，将继续生成")
            return None

    def _print_user_message(self, *lines: str, style: str = "default") -> None:
        """
        通过 ExecutionContext 输出用户友好的提示信息

        Args:
            *lines: 多行消息
            style: 样式（cyan, green, yellow, blue, dim, default）
        """
        # 合并多行消息
        message = "\n".join(lines)

        # 根据样式选择合适的 reporter 方法
        if style == "cyan":
            ExecutionContext.info(message)
        elif style == "green":
            ExecutionContext.success(message)
        elif style == "yellow":
            ExecutionContext.warning(message)
        elif style in ("blue", "dim", "default"):
            ExecutionContext.info(message)
        else:
            ExecutionContext.info(message)
