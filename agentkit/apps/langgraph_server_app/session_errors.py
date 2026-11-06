"""将原生 Thread 缺失转换为兼容会话接口的 404。"""

from contextlib import contextmanager

from httpx import HTTPStatusError
from starlette.exceptions import HTTPException


@contextmanager
def session_not_found():
    # 只处理已定位会话的 Thread 调用，避免把权限、网络或服务故障误判为不存在。
    try:
        yield
    except HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        # 不透出原生错误正文、URL 或异常链；这些内容可能带有内部执行信息。
        raise HTTPException(status_code=404, detail="Session not found") from None
