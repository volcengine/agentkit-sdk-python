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
import fnmatch
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ArchiveConfig:
    """Archive configuration for creating a project tarball."""

    source_dir: str = field(default=".", metadata={"description": "Source directory"})
    output_dir: str = field(
        default="/tmp", metadata={"description": "Output directory"}
    )
    archive_name: str = field(
        default="project",
        metadata={"description": "Archive base name (without extension)"},
    )

    dockerignore_path: Optional[str] = field(
        default=None,
        metadata={
            "description": "Path to .dockerignore file. If not provided, uses source_dir/.dockerignore when present."
        },
    )

    # Legacy include/exclude rules. Not used by default.
    # If .dockerignore exists, these rules are ignored.
    exclude_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class _DockerIgnoreRule:
    pattern: str
    negated: bool
    dir_only: bool
    anchored: bool
    has_slash: bool

    def matches(self, rel_posix_path: str, is_dir: bool) -> bool:
        rel_posix_path = rel_posix_path.lstrip("./")
        if rel_posix_path in ("", "."):
            return False

        # We evaluate patterns against all path prefixes so that a rule can match a directory
        # and implicitly apply to its descendants.
        parts = rel_posix_path.split("/")
        prefixes: List[str] = []
        for i in range(1, len(parts) + 1):
            prefixes.append("/".join(parts[:i]))

        if is_dir:
            dir_prefixes = prefixes
        else:
            dir_prefixes = prefixes[:-1]

        if self.dir_only:
            return self._matches_candidates(dir_prefixes)

        # A non-dir-only pattern can still match a directory; when it does,
        # it should affect the directory's descendants. So we match against
        # both the full path and directory prefixes.
        return self._matches_candidates(prefixes)

    def _matches_candidates(self, prefixes: List[str]) -> bool:
        if not prefixes:
            return False

        pat = self.pattern

        def _match_path(path: str, pattern: str) -> bool:
            path_parts = [p for p in path.split("/") if p]
            pattern_parts = [p for p in pattern.split("/") if p]

            # Fast path for single-segment patterns.
            if len(pattern_parts) == 1:
                return len(path_parts) == 1 and fnmatch.fnmatchcase(
                    path_parts[0], pattern_parts[0]
                )

            from functools import lru_cache

            @lru_cache(maxsize=None)
            def _dp(i: int, j: int) -> bool:
                if j == len(pattern_parts):
                    return i == len(path_parts)

                token = pattern_parts[j]
                if token == "**":
                    # Match zero or more segments.
                    return _dp(i, j + 1) or (i < len(path_parts) and _dp(i + 1, j))

                if i >= len(path_parts):
                    return False

                if fnmatch.fnmatchcase(path_parts[i], token):
                    return _dp(i + 1, j + 1)

                return False

            return _dp(0, 0)

        if self.anchored:
            candidates = prefixes
            return any(_match_path(c, pat) for c in candidates)

        # Non-anchored matching.
        if not self.has_slash:
            # Match against any path component.
            parts = prefixes[-1].split("/")
            return any(fnmatch.fnmatchcase(p, pat) for p in parts)

        # Pattern contains '/': match at any depth by matching against any suffix of any prefix.
        for prefix in prefixes:
            prefix_parts = prefix.split("/")
            for i in range(len(prefix_parts)):
                suffix = "/".join(prefix_parts[i:])
                if _match_path(suffix, pat):
                    return True
        return False


class _DockerIgnoreMatcher:
    def __init__(self, rules: List[_DockerIgnoreRule]):
        self._rules = rules
        self._has_negations = any(r.negated for r in rules)

    @classmethod
    def from_path(cls, dockerignore_path: Path) -> "_DockerIgnoreMatcher":
        rules: List[_DockerIgnoreRule] = []

        try:
            content = dockerignore_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read .dockerignore at {dockerignore_path}: {e}")
            return cls([])

        for raw_line in content.splitlines():
            line = raw_line.rstrip("\n\r")
            stripped = line.strip()
            if not stripped:
                continue

            # Docker treats a leading '#' as a comment; '\#' escapes it.
            if stripped.startswith("#"):
                continue
            if stripped.startswith("\\#"):
                stripped = stripped[1:]

            negated = False
            if stripped.startswith("\\!"):
                stripped = stripped[1:]
            elif stripped.startswith("!"):
                negated = True
                stripped = stripped[1:].strip()

            if not stripped:
                continue

            anchored = stripped.startswith("/")
            if anchored:
                stripped = stripped[1:]

            dir_only = stripped.endswith("/")
            if dir_only:
                stripped = stripped.rstrip("/")

            stripped = stripped.lstrip("./")
            if not stripped:
                continue

            has_slash = "/" in stripped
            rules.append(
                _DockerIgnoreRule(
                    pattern=stripped,
                    negated=negated,
                    dir_only=dir_only,
                    anchored=anchored,
                    has_slash=has_slash,
                )
            )

        return cls(rules)

    def should_include(self, rel_posix_path: str, is_dir: bool) -> bool:
        included = True
        for rule in self._rules:
            if rule.matches(rel_posix_path, is_dir=is_dir):
                included = True if rule.negated else False
        return included

    @property
    def has_negations(self) -> bool:
        return self._has_negations


class ProjectArchiver:
    """Create a tar.gz archive for a project directory."""

    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.source_path = Path(config.source_dir).resolve()
        self.output_path = Path(config.output_dir).resolve()

        dockerignore_path = None
        if config.dockerignore_path:
            candidate = Path(config.dockerignore_path)
            if candidate.is_file():
                dockerignore_path = candidate

        if dockerignore_path is None:
            candidate = self.source_path / ".dockerignore"
            if candidate.is_file():
                dockerignore_path = candidate

        self._dockerignore_path = dockerignore_path
        self._dockerignore_matcher = (
            _DockerIgnoreMatcher.from_path(dockerignore_path)
            if dockerignore_path is not None
            else None
        )

        if self._dockerignore_path is not None:
            logger.info(f"Using .dockerignore rules from: {self._dockerignore_path}")
        else:
            logger.info(
                "No .dockerignore found; archiving will include all files by default."
            )

    def collect_files_to_include(self) -> List[Path]:
        """Collect files that should be included in the project archive."""
        return self._get_files_to_include()

    def create_archive(self, files_to_include: Optional[List[Path]] = None) -> str:
        try:
            logger.info(f"Creating project archive from: {self.source_path}")
            self.output_path.mkdir(parents=True, exist_ok=True)
            archive_path = self.output_path / f"{self.config.archive_name}.tar.gz"
            if files_to_include is None:
                files_to_include = self._get_files_to_include()

            if not files_to_include:
                raise ValueError(
                    "No files matched for archiving. Check your .dockerignore rules."
                )

            with tarfile.open(archive_path, "w:gz") as tar:
                for file_path in files_to_include:
                    arcname = file_path.relative_to(self.source_path)
                    tar.add(file_path, arcname=arcname)
                    logger.debug(f"Adding file to archive: {arcname}")

            logger.info(
                f"Archive created: {archive_path} (files={len(files_to_include)})"
            )
            return str(archive_path)

        except Exception:
            logger.exception(
                "Failed to create project archive",
                extra={
                    "source_dir": str(self.source_path),
                    "output_dir": str(self.output_path),
                },
            )
            raise

    def _get_files_to_include(self) -> List[Path]:
        files_to_include = []

        try:
            # If .dockerignore contains negation rules, pruning directories can drop
            # later re-inclusions. In that case, we keep walking and filter per-path.
            for root, dirs, files in os.walk(self.source_path):
                root_path = Path(root)

                # Safe optimization: if there are no negations, we can skip excluded
                # directories to avoid unnecessary traversal.
                if (
                    self._dockerignore_matcher is not None
                    and not self._dockerignore_matcher.has_negations
                ):
                    kept_dirs: List[str] = []
                    for d in dirs:
                        dir_path = root_path / d
                        rel_posix = dir_path.relative_to(self.source_path).as_posix()
                        if self._dockerignore_matcher.should_include(
                            rel_posix, is_dir=True
                        ):
                            kept_dirs.append(d)
                    dirs[:] = kept_dirs

                for file_name in files:
                    file_path = root_path / file_name

                    if self._should_include_file(file_path):
                        files_to_include.append(file_path)

            self._force_include_required_files(files_to_include)

            return files_to_include

        except Exception:
            logger.exception(
                "Failed to collect files for archiving",
                extra={"source_dir": str(self.source_path)},
            )
            raise

    def _force_include_required_files(self, files_to_include: List[Path]) -> None:
        """Force-include files required by remote build pipelines.

        The project archive is used as remote build context (e.g. CodePipeline + BuildKit).
        Some files must exist in the extracted workspace even if users accidentally exclude
        them via `.dockerignore`.
        """

        # Remote pipelines expect a Dockerfile at the project root.
        dockerfile_path = self.source_path / "Dockerfile"
        if dockerfile_path.is_file() and dockerfile_path not in files_to_include:
            files_to_include.append(dockerfile_path)

        # Keep .dockerignore in the archive for transparency/debuggability.
        dockerignore_path = self.source_path / ".dockerignore"
        if dockerignore_path.is_file() and dockerignore_path not in files_to_include:
            files_to_include.append(dockerignore_path)

    def _should_include_file(self, file_path: Path) -> bool:
        try:
            rel_posix = file_path.relative_to(self.source_path).as_posix()

            # Preferred behavior: follow .dockerignore exactly when present.
            if self._dockerignore_matcher is not None:
                return self._dockerignore_matcher.should_include(
                    rel_posix, is_dir=False
                )

            # No .dockerignore: include everything by default.
            if not self.config.exclude_patterns and not self.config.include_patterns:
                return True

            # Legacy behavior (only when explicitly configured).
            for pattern in self.config.exclude_patterns:
                if pattern and self._match_pattern(rel_posix, pattern):
                    return False

            if not self.config.include_patterns:
                return True

            return any(
                self._match_pattern(rel_posix, pattern)
                for pattern in self.config.include_patterns
            )

        except Exception:
            return False

    def _match_pattern(self, text: str, pattern: str) -> bool:
        return fnmatch.fnmatchcase(text, pattern)

    def get_project_info(self) -> dict:
        try:
            files = self._get_files_to_include()

            info = {
                "source_dir": str(self.source_path),
                "total_files": len(files),
                "total_size": sum(f.stat().st_size for f in files),
                "files": [str(f.relative_to(self.source_path)) for f in files],
            }

            return info

        except Exception:
            logger.exception(
                "Failed to collect project info",
                extra={"source_dir": str(self.source_path)},
            )
            return {}


def create_project_archive(
    source_dir: str = ".",
    output_dir: str = "/tmp",
    archive_name: Optional[str] = None,
    dockerignore_path: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
) -> str:
    """Create a project tarball for uploading/building.

    Behavior priority:
    - If `.dockerignore` exists (either via `dockerignore_path` or in `source_dir`), it is
      used as the single source of truth for filtering.
    - If no `.dockerignore` exists, all files are included by default.

    `exclude_patterns`/`include_patterns` are legacy options kept for backward compatibility.
    They are only applied when `.dockerignore` is not present.
    """
    try:
        source_path = Path(source_dir).resolve()

        if not archive_name:
            archive_name = source_path.name

        config = ArchiveConfig(
            source_dir=source_dir,
            output_dir=output_dir,
            archive_name=archive_name,
            dockerignore_path=dockerignore_path,
        )

        # Only used when .dockerignore is not present.
        if exclude_patterns:
            config.exclude_patterns = exclude_patterns
        if include_patterns:
            config.include_patterns = include_patterns

        archiver = ProjectArchiver(config)
        return archiver.create_archive()

    except Exception:
        logger.exception(
            "Failed to create project archive",
            extra={
                "source_dir": source_dir,
                "output_dir": output_dir,
                "archive_name": archive_name,
            },
        )
        raise
