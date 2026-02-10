#!/bin/sh

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

set -eu

# Generic build script for Go projects used inside the builder image.
# Environment variables expected (builder sets BUILD_OUTPUT_DIR, BUILD_BINARY_NAME):
#  BUILD_OUTPUT_DIR - where to place the binary (default: /app)
#  BUILD_BINARY_NAME - binary name (fallback to current dir name)
# Optional:
#  ENTRY - go build target (file, dir or package); default is '.'

OUTPUT_DIR=${BUILD_OUTPUT_DIR:-/app}
BIN_NAME=${BUILD_BINARY_NAME:-${BINARY_NAME:-$(basename "$(pwd)")}}
ENTRY=${ENTRY:-.}

mkdir -p "${OUTPUT_DIR}"

# Prefer module-aware builds if go.mod exists
if [ -f go.mod ]; then
  echo "Building module-aware: ENTRY='${ENTRY}' BIN='${BIN_NAME}'"
  export GOPROXY=${GOPROXY:-https://goproxy.cn}
  CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o "${OUTPUT_DIR}/${BIN_NAME}" ${ENTRY}
else
  echo "No go.mod found, using standard go build: ENTRY='${ENTRY}' BIN='${BIN_NAME}'"
  CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o "${OUTPUT_DIR}/${BIN_NAME}" ${ENTRY}
fi

echo "Built ${OUTPUT_DIR}/${BIN_NAME}"
