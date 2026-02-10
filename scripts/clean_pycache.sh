#!/bin/bash

# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

# Clean all __pycache__ directories and .pyc files in the project

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Cleaning __pycache__ directories in: $PROJECT_ROOT"

# Find and remove all __pycache__ directories
pycache_count=$(find "$PROJECT_ROOT" -type d -name "__pycache__" | wc -l)
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Find and remove all .pyc files
pyc_count=$(find "$PROJECT_ROOT" -type f -name "*.pyc" | wc -l)
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

# Find and remove all .pyo files
pyo_count=$(find "$PROJECT_ROOT" -type f -name "*.pyo" | wc -l)
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true

echo "Cleaned:"
echo "  - $pycache_count __pycache__ directories"
echo "  - $pyc_count .pyc files"
echo "  - $pyo_count .pyo files"
echo "Done!"
