import queue


class ApprovalStore:
    # queue.Queue() 用来在不同请求线程之间传递审批结果
    def __init__(self):
        self._queues: dict[str, queue.Queue] = {}

    # 由 /agent/approve 调用，把用户选择放入队列
    def decide(self, request_id: str, approved: bool) -> None:
        self._queues.setdefault(request_id, queue.Queue()).put(approved)

    # 由 Agent 流式生成器调用，如果用户还没点击，就暂时等待
    def wait(self, request_id: str, timeout: float = 120) -> bool:
        queue_obj = self._queues.setdefault(request_id, queue.Queue())

        try:
            return queue_obj.get(timeout=timeout)
        except queue.Empty: # 返回 False，避免请求永久卡住
            return False

    def clear(self, request_id: str) -> None:
        self._queues.pop(request_id, None)



approval_store = ApprovalStore()

