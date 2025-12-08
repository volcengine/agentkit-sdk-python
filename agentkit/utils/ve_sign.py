# Copyright 2025 ByteDance and/or its affiliates.
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

import datetime
import hashlib
import hmac
import os
from urllib.parse import quote

import requests

Service = ""
Version = ""
Region = ""
Host = ""
ContentType = ""
Scheme = "https"


def norm_query(params):
    query = ""
    for key in sorted(params.keys()):
        if isinstance(params[key], list):
            for k in params[key]:
                query = (
                    query + quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
                )
        else:
            query = (
                query
                + quote(key, safe="-_.~")
                + "="
                + quote(params[key], safe="-_.~")
                + "&"
            )
    query = query[:-1]
    return query.replace("+", "%20")


# 第一步：准备辅助函数。
# sha256 非对称加密
def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


# sha256 hash算法
def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# 第二步：签名请求函数
def request(method, date, query, header, ak, sk, action, body):
    # 第三步：创建身份证明。其中的 Service 和 Region 字段是固定的。ak 和 sk 分别代表
    # AccessKeyID 和 SecretAccessKey。同时需要初始化签名结构体。一些签名计算时需要的属性也在这里处理。
    # 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": Service,
        "region": Region,
    }
    # 初始化签名结构体
    request_param = {
        "body": body,
        "host": Host,
        "path": "/",
        "method": method,
        "content_type": ContentType,
        "date": date,
        "query": {"Action": action, "Version": Version, **query},
    }
    if body is None:
        request_param["body"] = ""
    # 第四步：接下来开始计算签名。在计算签名前，先准备好用于接收签算结果的 signResult 变量，并设置一些参数。
    # 初始化签名结果的结构体
    x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }
    # 第五步：计算 Signature 签名。
    signed_headers_str = ";".join(
        ["content-type", "host", "x-content-sha256", "x-date"]
    )
    # signed_headers_str = signed_headers_str + ";x-security-token"
    canonical_request_str = "\n".join(
        [
            request_param["method"].upper(),
            request_param["path"],
            norm_query(request_param["query"]),
            "\n".join(
                [
                    "content-type:" + request_param["content_type"],
                    "host:" + request_param["host"],
                    "x-content-sha256:" + x_content_sha256,
                    "x-date:" + x_date,
                ]
            ),
            "",
            signed_headers_str,
            x_content_sha256,
        ]
    )

    # 打印正规化的请求用于调试比对
    # print(canonical_request_str)
    hashed_canonical_request = hash_sha256(canonical_request_str)

    # 打印hash值用于调试比对
    # print(hashed_canonical_request)
    credential_scope = "/".join(
        [short_x_date, credential["region"], credential["service"], "request"]
    )
    string_to_sign = "\n".join(
        ["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request]
    )

    # 打印最终计算的签名字符串用于调试比对
    # print(string_to_sign)
    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    sign_result["Authorization"] = (
        "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
            credential["access_key_id"] + "/" + credential_scope,
            signed_headers_str,
            signature,
        )
    )
    header = {**header, **sign_result}
    # header = {**header, **{"X-Security-Token": SessionToken}}
    # 第六步：将 Signature 签名写入 HTTP Header 中，并发送 HTTP 请求。
    r = requests.request(
        method=method,
        url=f"{Scheme}://{request_param['host']}{request_param['path']}",
        headers=header,
        params=request_param["query"],
        data=request_param["body"],
    )
    return r.json()


def ve_request(
    request_body: dict,
    action: str,
    ak: str,
    sk: str,
    service: str,
    version: str,
    region: str,
    host: str,
    header: dict = {},
    content_type: str = "application/json",
    scheme: str = "https",
):
    # response_body = request("Get", datetime.datetime.utcnow(), {}, {}, AK, SK, "ListUsers", None)
    # print(response_body)
    # 以下参数视服务不同而不同，一个服务内通常是一致的
    global Service
    Service = service
    global Version
    Version = version
    global Region
    Region = region
    global Host
    Host = host
    global ContentType
    ContentType = content_type
    global Scheme
    Scheme = scheme or "https"

    AK = ak
    SK = sk

    now = datetime.datetime.utcnow()

    # Body的格式需要配合Content-Type，API使用的类型请阅读具体的官方文档，如:json格式需要json.dumps(obj)
    # response_body = request("GET", now, {"Limit": "2"}, {}, AK, SK, "ListUsers", None)
    import json

    try:
        response_body = request(
            "POST", now, {}, header, AK, SK, action, json.dumps(request_body)
        )
        check_error(response_body)
        return response_body
    except Exception as e:
        raise e


def check_error(response: dict) -> None:
    if "Error" in response["ResponseMetadata"]:
        error_code = response["ResponseMetadata"]["Error"]["Code"]
        error_message = response["ResponseMetadata"]["Error"]["Message"]
        action = response["ResponseMetadata"]["Action"]
        raise ValueError(
            f"Error when ve_request {action}: {error_code} {error_message}, res: {response}"
        )


def get_volc_ak_sk_region(service: str = ""):
    """获取火山引擎凭证

    优先级：
    1. 服务特定环境变量（VOLCENGINE_CR_ACCESS_KEY 等）
    2. 通用环境变量（VOLCENGINE_ACCESS_KEY 等）
    3. 全局配置文件（~/.agentkit/config.yaml）
    4. 抛出异常

    Args:
        service: 服务名称（CR/AGENTKIT/TOS/IAM等），用于查找特定环境变量

    Returns:
        (access_key, secret_key, region) 元组

    Raises:
        ValueError: 如果无法获取有效的凭证
    """
    ak, sk, region = "", "", ""

    # 1. 尝试服务特定环境变量
    if service.upper() == "CR":
        # 优先使用新的 VOLCENGINE_* 环境变量，兼容旧的 VOLC_* 环境变量
        ak = os.getenv("VOLCENGINE_CR_ACCESS_KEY") or os.getenv("VOLC_CR_ACCESSKEY")
        sk = os.getenv("VOLCENGINE_CR_SECRET_KEY") or os.getenv("VOLC_CR_SECRETKEY")
        region = os.getenv("VOLCENGINE_CR_REGION") or os.getenv("VOLC_CR_REGION")
    elif service.upper() == "AGENTKIT":
        # 优先使用新的 VOLCENGINE_* 环境变量，兼容旧的 VOLC_* 环境变量
        ak = os.getenv("VOLCENGINE_AGENTKIT_ACCESS_KEY") or os.getenv(
            "VOLC_AGENTKIT_ACCESSKEY"
        )
        sk = os.getenv("VOLCENGINE_AGENTKIT_SECRET_KEY") or os.getenv(
            "VOLC_AGENTKIT_SECRETKEY"
        )
        region = os.getenv("VOLCENGINE_AGENTKIT_REGION") or os.getenv(
            "VOLC_AGENTKIT_REGION"
        )
    elif service.upper() == "TOS":
        # 优先使用新的 VOLCENGINE_* 环境变量，兼容旧的 VOLC_* 环境变量
        ak = os.getenv("VOLCENGINE_TOS_ACCESS_KEY") or os.getenv("VOLC_TOS_ACCESSKEY")
        sk = os.getenv("VOLCENGINE_TOS_SECRET_KEY") or os.getenv("VOLC_TOS_SECRETKEY")
        region = os.getenv("VOLCENGINE_TOS_REGION") or os.getenv("VOLC_TOS_REGION")

    # 2. 如果服务特定环境变量不完整，尝试通用环境变量
    if not all([ak, sk, region]):
        # 优先使用新的 VOLCENGINE_* 环境变量，兼容旧的 VOLC_* 环境变量
        ak = ak or os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("VOLC_ACCESSKEY")
        sk = sk or os.getenv("VOLCENGINE_SECRET_KEY") or os.getenv("VOLC_SECRETKEY")
        region = region or os.getenv("VOLCENGINE_REGION") or os.getenv("VOLC_REGION")

    # 3. 【新增】如果环境变量仍不完整，尝试全局配置
    if not all([ak, sk]):
        try:
            # 延迟导入，避免循环依赖
            from agentkit.toolkit.config.global_config import get_global_config

            global_config = get_global_config()
            ak = ak or global_config.volcengine.access_key
            sk = sk or global_config.volcengine.secret_key
            region = region or global_config.volcengine.region
        except Exception:
            # 全局配置加载失败，继续原有逻辑
            pass

    # 4. 设置默认 region
    region = region if region else "cn-beijing"

    # 5. 验证必需字段
    if not ak or not sk:
        raise ValueError(
            "未找到火山引擎访问凭证。请设置环境变量 VOLCENGINE_ACCESS_KEY 和 "
            "VOLCENGINE_SECRET_KEY (export VOLCENGINE_ACCESS_KEY=your_access_key; export VOLCENGINE_SECRET_KEY=your_secret_key)，或在全局配置文件 ~/.agentkit/config.yaml 中配置"
        )

    return ak, sk, region


def get_volc_agentkit_host_info():
    try:
        from agentkit.toolkit.config.global_config import get_global_config

        gc = get_global_config()
        if gc.agentkit_host:
            host = gc.agentkit_host
        else:
            host = os.getenv("VOLCENGINE_AGENTKIT_HOST") or os.getenv(
                "VOLC_AGENTKIT_HOST"
            )
    except Exception:
        host = os.getenv("VOLCENGINE_AGENTKIT_HOST") or os.getenv("VOLC_AGENTKIT_HOST")
    api_version = os.getenv("VOLCENGINE_AGENTKIT_API_VERSION") or os.getenv(
        "VOLC_AGENTKIT_API_VERSION"
    )
    service_code = os.getenv("VOLCENGINE_AGENTKIT_SERVICE") or os.getenv(
        "VOLC_AGENTKIT_SERVICE"
    )
    return (
        host if host else "open.volcengineapi.com",
        api_version if api_version else "2025-10-30",
        service_code if service_code else "agentkit",
    )


def get_identity_host_info():
    host = os.getenv("VOLCENGINE_IDENTITY_HOST") or os.getenv("VOLC_IDENTITY_HOST")
    api_version = os.getenv("VOLCENGINE_IDENTITY_API_VERSION") or os.getenv(
        "VOLC_IDENTITY_API_VERSION"
    )
    service_code = os.getenv("VOLCENGINE_IDENTITY_SERVICE") or os.getenv(
        "VOLC_IDENTITY_SERVICE"
    )
    region = os.getenv("VOLCENGINE_IDENTITY_REGION") or os.getenv(
        "VOLC_IDENTITY_REGION"
    )
    return (
        host if host else "open.volcengineapi.com",
        api_version if api_version else "2023-10-01",
        service_code if service_code else "cis_test",
        region if region else "cn-beijing",
    )
