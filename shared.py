"""
共享层 - 对应知识点: 多 Agent 的「状态共享」+「通信方式」问题

两种经典模式：
1. Blackboard（黑板）: 共享状态区，所有 Agent 都能读写（解耦）
2. MessageBus（消息总线）: 结构化通信，可追溯
"""

from datetime import datetime


class Blackboard:
    """黑板模式 - 共享状态区。类比办公室白板。"""

    def __init__(self):
        self._state = {
            "feature_request": "",
            "tasks": [],
            "code_artifacts": {},
            "review_reports": [],
            "history": [],
            "status": "init",
        }

    def read(self, key=None):
        if key is None:
            return dict(self._state)
        return self._state.get(key)

    def write(self, key, value):
        self._state[key] = value
        self._state["history"].append({
            "action": f"write:{key}",
            "at": datetime.now().isoformat(),
        })

    def append(self, list_key, item):
        self._state[list_key] = self._state.get(list_key, []) + [item]
        self._state["history"].append({
            "action": f"append:{list_key}",
            "at": datetime.now().isoformat(),
        })

    def snapshot(self):
        return {
            "status": self._state["status"],
            "tasks_done": len([t for t in self._state["tasks"] if t.get("done")]),
            "tasks_total": len(self._state["tasks"]),
            "code_count": len(self._state["code_artifacts"]),
            "reviews": len(self._state["review_reports"]),
        }


class MessageBus:
    """消息总线 - 结构化通信。类比内部邮件。"""

    def __init__(self):
        self._messages = []

    def send(self, sender, receiver, content, msg_type="info"):
        msg = {
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "type": msg_type,
            "at": datetime.now().isoformat(),
        }
        self._messages.append(msg)
        return msg

    def receive(self, receiver):
        return [m for m in self._messages if m["receiver"] == receiver]

    def log(self):
        for m in self._messages:
            print(f"  [{m['type']}] {m['sender']} -> {m['receiver']}: {m['content'][:60]}")
