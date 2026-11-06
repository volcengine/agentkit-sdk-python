"""A2A 任务保存边界的观测适配，不维护第二份任务状态。"""

from a2a.server.tasks import InMemoryTaskStore
from a2a.server.tasks.task_store import TaskStore
from opentelemetry import trace


class ObservedTaskStore(TaskStore):
    def __init__(self, delegate: TaskStore):
        self.delegate = delegate

    async def save(self, task, context=None):
        # 只记录协议字段；正文、产物及身份上下文不进入新增观测数据。
        with trace.get_tracer("agentkit.a2a_app").start_as_current_span(
            "a2a.task.save", record_exception=False, set_status_on_exception=False
        ) as span:
            span.set_attribute("agentkit.task.id", task.id)
            span.set_attribute("gen_ai.session.id", task.context_id)
            try:
                await self.delegate.save(task, context=context)
            except Exception as error:
                span.set_attribute("error.type", type(error).__name__)
                span.set_status(trace.StatusCode.ERROR)
                raise
            # 保存成功才记录状态。内存存储的保存不代表跨进程持久化。
            state = task.status.state.value
            span.add_event("a2a.task.state.saved", {
                "agentkit.task.state": state,
                "agentkit.task.status_timestamp": task.status.timestamp,
            })

    async def get(self, task_id, context=None):
        return await self.delegate.get(task_id, context=context)

    async def delete(self, task_id, context=None):
        return await self.delegate.delete(task_id, context=context)


def observe_task_store(store):
    # 保持外部提供的存储与上下文协议，不增加队列或替换持久化实现。
    if isinstance(store, ObservedTaskStore):
        return store
    if store is None:
        store = InMemoryTaskStore()
    return ObservedTaskStore(store) if isinstance(store, TaskStore) else store
