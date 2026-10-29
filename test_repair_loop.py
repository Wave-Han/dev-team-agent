"""
Day 11 repair-loop tests - TDD for the no-progress guard.

Pairing discipline (same as the eval regression pins):
- test 1 asserts the guard CATCHES a stalled repair loop with a diagnosis
- test 2 asserts the guard does NOT kill a legitimate, effective repair

Both are RED before the guard exists:
- today a leaky coder yields status="done" (CRITICAL silently swallowed)
- today critical findings survive into the final report
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agents import PlannerAgent, CoderAgent
from orchestrator import TeamOrchestrator
from deadloop_demo import LeakyCoder


class StubPlanner(PlannerAgent):
    """Planner stub: a single task, keeping the repro minimal."""

    def _simulate(self, feature):
        return [{"id": "T1", "desc": "implement login", "done": False}]


class FixingCoder(CoderAgent):
    """Leaks on the first pass, writes clean code on every later call.

    Models an LLM whose repair actually works: one routing back is enough.
    """

    def _simulate(self, task):
        if self.turns_used == 1:
            return f"# Task {task['id']}\nPASSWORD = 'admin123'\n"
        return f"# Task {task['id']}: fixed\ndef handle_{task['id'].lower()}():\n    pass\n"


def make_team(coder):
    cfg = {"api_key": "", "global_max_turns": 12}
    team = TeamOrchestrator(cfg)
    team.planner = StubPlanner(team.bb, team.bus, cfg)
    team.coder = coder(team.bb, team.bus, cfg)
    return team


def test_stalled_repair_loop_fails_fast_with_diagnosis():
    print("=" * 50)
    print("测试 1: 无进展死循环 -> 提前失败并给出诊断")
    print("=" * 50)
    team = make_team(LeakyCoder)
    result = team.execute("实现登录功能")

    assert result["status"] == "failed", (
        f"expected failed, got {result['status']} (CRITICAL swallowed?)")
    assert "无进展" in result["reason"], (
        f"expected no-progress diagnosis, got: {result['reason']}")
    # Bounded waste: guard must fire before the dumb breakers do.
    assert team.global_turns <= 8, f"burned {team.global_turns} ticks - guard too late"
    assert team.coder.turns_used <= 3, "wasted more than 2 repair attempts"
    print(f"  诊断: {result['reason']}")
    print(f"  消耗: global={team.global_turns}/12, coder={team.coder.turns_used}/5")
    print("  [PASS]\n")


def test_effective_repair_still_completes():
    print("=" * 50)
    print("测试 2: 有效修复不被误杀(回归钉)")
    print("=" * 50)
    team = make_team(FixingCoder)
    result = team.execute("实现登录功能")

    assert result["status"] == "done", f"expected done, got {result['status']}"
    assert "CRITICAL" not in result["report"], (
        "final report still contains CRITICAL findings")
    assert team.global_turns <= 8, f"unexpected turn burn: {team.global_turns}"
    print(f"  修复 1 轮后通过, global={team.global_turns}/12")
    print("  [PASS]\n")


if __name__ == "__main__":
    print("\nRepair-loop guard tests\n")
    test_stalled_repair_loop_fails_fast_with_diagnosis()
    test_effective_repair_still_completes()
    print("=" * 50)
    print("全部通过!")
    print("=" * 50)
