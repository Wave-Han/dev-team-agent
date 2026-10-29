"""
离线测试 - 无需 API Key 验证多 Agent 协作流程
测试: Blackboard/MessageBus、单Agent、完整流程、maxTurns、安全检测、Human-in-the-Loop
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared import Blackboard, MessageBus
from agents import PlannerAgent, CoderAgent, ReviewerAgent
from orchestrator import TeamOrchestrator


def test_shared():
    print("=" * 50)
    print("测试 1: Blackboard + MessageBus")
    print("=" * 50)
    bb = Blackboard()
    bb.write("feature_request", "test feature")
    bb.append("tasks", {"id": "T1", "done": False})
    bb.append("tasks", {"id": "T2", "done": False})
    assert bb.read("feature_request") == "test feature"
    assert len(bb.read("tasks")) == 2
    print(f"  Blackboard: 写入/读取 OK, history={len(bb.read('history'))} 条")

    bus = MessageBus()
    bus.send("planner", "coder", "任务已拆好", "task")
    bus.send("reviewer", "human", "发现 CRITICAL", "approval")
    assert len(bus.receive("coder")) == 1
    assert len(bus.receive("human")) == 1
    print(f"  MessageBus: 收发消息 OK")
    print("  [PASS]\n")


def test_single_agents():
    print("=" * 50)
    print("测试 2: 单个 Agent（离线模拟）")
    print("=" * 50)
    cfg = {"api_key": ""}
    bb = Blackboard()
    bus = MessageBus()

    planner = PlannerAgent(bb, bus, cfg)
    tasks = planner.run("实现登录功能")
    assert len(tasks) == 4
    print(f"  Planner: 拆出 {len(tasks)} 个任务")

    coder = CoderAgent(bb, bus, cfg)
    code = coder.run(tasks[0])
    assert "def handle" in code
    assert "T1" in bb.read("code_artifacts")
    print(f"  Coder: 生成代码 {len(code)} 字符")

    reviewer = ReviewerAgent(bb, bus, cfg)
    report = reviewer.run()
    assert "代码审查报告" in report
    assert "TODO" in report
    print(f"  Reviewer: 产出报告，检出 TODO")
    print("  [PASS]\n")


def test_full_flow():
    print("=" * 50)
    print("测试 3: 完整协作流程（Orchestrator）")
    print("=" * 50)
    cfg = {"api_key": "", "global_max_turns": 12}
    team = TeamOrchestrator(cfg)
    result = team.execute("实现一个用户注册功能")

    assert result["status"] == "done"
    snap = result["snapshot"]
    assert snap["tasks_done"] == snap["tasks_total"]
    assert snap["code_count"] == 4
    assert snap["reviews"] >= 1
    print(f"\n  结果: status={result['status']}, turns={result['global_turns']}")
    print("  [PASS]\n")


def test_maxturns_safety():
    print("=" * 50)
    print("测试 4: maxTurns 安全阀（防失控）")
    print("=" * 50)
    cfg = {"api_key": "", "global_max_turns": 1}
    team = TeamOrchestrator(cfg)
    result = team.execute("触发限制的功能")
    assert result["status"] == "failed"
    assert "超限" in result["reason"]
    print(f"  正确触发保护: {result['reason']}")
    print("  [PASS]\n")


def test_security_detection():
    print("=" * 50)
    print("测试 5: 安全检测（集成 Code Review 知识）")
    print("=" * 50)
    cfg = {"api_key": ""}
    bb = Blackboard()
    bus = MessageBus()
    bb.write("code_artifacts", {
        "T1": "password = 'secret123'",
        "T2": "def f():\n  pass",
    })
    reviewer = ReviewerAgent(bb, bus, cfg)
    report = reviewer.run()
    assert "CRITICAL" in report
    assert "硬编码密钥" in report
    assert len(bus.receive("human")) == 1
    print(f"  CRITICAL 检出 + 触发人工确认 OK")
    print("  [PASS]\n")


if __name__ == "__main__":
    print("\n多 Agent 软件开发团队 -- 离线测试\n")
    test_shared()
    test_single_agents()
    test_full_flow()
    test_maxturns_safety()
    test_security_detection()
    print("=" * 50)
    print("全部测试通过! 多 Agent 协作系统工作正常")
    print("=" * 50)
