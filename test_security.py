"""
Day 12 security tests - TDD for injection defenses.

Layered defense under test:
  1. InputSanitizer at the pipeline boundary (reject override payloads)
  2. Output invariant (an empty task list must NOT count as success)
  3. Existing downstream layers (reviewer + Day-11 guard) stay untouched

Pairing discipline (third appearance of the same meta-rule):
- test 1 kills the attack
- test 2 is the pin: a BENIGN input containing "忽略" must still pass -
  a filter that blocks everything would "solve" injection by breaking
  the product (the security flavor of the P/R seesaw)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agents import PlannerAgent
from orchestrator import TeamOrchestrator
from injection_demo import ATTACK_A

CFG = {"api_key": "", "global_max_turns": 12}


class EmptyStubPlanner(PlannerAgent):
    """Planner stub that returns zero tasks (injection or plain failure)."""

    def _simulate(self, feature):
        return []


def test_injection_override_rejected():
    print("=" * 50)
    print("测试 1: 注入载荷必须在入口被拒绝")
    print("=" * 50)
    team = TeamOrchestrator(dict(CFG))
    result = team.execute(ATTACK_A)
    assert result["status"] == "failed", (
        f"expected rejected, got {result['status']} (no boundary defense?)")
    assert "注入" in result["reason"], (
        f"expected injection diagnosis, got: {result['reason']}")
    print(f"  拒绝原因: {result['reason']}")
    print("  [PASS]\n")


def test_benign_input_containing_ignore_passes():
    print("=" * 50)
    print("测试 2: 正常含'忽略'一词的需求不被误杀(回归钉)")
    print("=" * 50)
    team = TeamOrchestrator(dict(CFG))
    result = team.execute("实现一个忽略大小写的登录功能")
    assert result["status"] == "done", (
        f"benign input blocked - filter too wide: {result.get('reason')}")
    print("  正常需求照常完成")
    print("  [PASS]\n")


def test_empty_task_list_rejected():
    print("=" * 50)
    print("测试 3: 空任务列表不许算成功(输出不变量)")
    print("=" * 50)
    team = TeamOrchestrator(dict(CFG))
    team.planner = EmptyStubPlanner(team.bb, team.bus, dict(CFG))
    result = team.execute("任何需求")
    assert result["status"] == "failed", (
        f"expected failed, got {result['status']} (silent no-op success?)")
    assert "空任务列表" in result["reason"]
    print(f"  拒绝原因: {result['reason']}")
    print("  [PASS]\n")


if __name__ == "__main__":
    print("\nInjection defense tests\n")
    test_injection_override_rejected()
    test_benign_input_containing_ignore_passes()
    test_empty_task_list_rejected()
    print("=" * 50)
    print("全部通过!")
    print("=" * 50)
