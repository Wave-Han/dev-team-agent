"""
Day 13 hallucination tests - TDD for evidence anchoring + verification.

Fix under test: every POSITIVE finding must cite an evidence snippet
that actually exists in the artifact. Unverifiable findings are
QUARANTINED (reported separately, never routed to repair) - they are
not silently dropped: transparency about suspected hallucinations.

Pairing discipline (4th appearance of the meta-rule):
- tests 1/3 kill hallucinations (phantom no longer fails the pipeline)
- test 2 is the pin: REAL findings must survive verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from deadloop_demo import StubPlanner
from hallucination_demo import HallucinatingReviewer
from orchestrator import TeamOrchestrator

CFG = {"api_key": "", "global_max_turns": 12}


def test_phantom_critical_quarantined_pipeline_done():
    print("=" * 50)
    print("测试 1: 幻觉发现被隔离,管线不再为幽灵失败")
    print("=" * 50)
    team = TeamOrchestrator(dict(CFG))
    team.planner = StubPlanner(team.bb, team.bus, dict(CFG))
    team.reviewer = HallucinatingReviewer(team.bb, team.bus, dict(CFG))
    result = team.execute("实现登录功能")

    assert result["status"] == "done", (
        f"pipeline still failed on a phantom: {result.get('reason')}")
    assert "隔离" in result["report"], "quarantine section missing from report"
    assert "SQL 注入风险" in result["report"], (
        "hallucinated finding must stay VISIBLE (quarantined, not erased)")
    assert "CRITICAL" not in result["report"], (
        "phantom must not be confirmed as CRITICAL")
    assert team.global_turns <= 3, (
        f"repair loop burned {team.global_turns} turns on a phantom")
    print(f"  status=done, turns={team.global_turns}/12, 幻觉 2 条入隔离区")
    print("  [PASS]\n")


def test_real_findings_survive_verification():
    print("=" * 50)
    print("测试 2: 真实发现不被误杀(回归钉)")
    print("=" * 50)
    team = TeamOrchestrator(dict(CFG))
    result = team.execute("实现一个用户注册功能")
    assert result["status"] == "done"
    assert "未完成的 TODO" in result["report"], (
        "real finding (TODO) lost after verification - verifier too strict")
    assert "隔离" not in result["report"], (
        "real findings should not land in quarantine")
    print("  真实 TODO 发现照常确认")
    print("  [PASS]\n")


def test_verifier_rules():
    print("=" * 50)
    print("测试 3: 验证器三条规则(单元)")
    print("=" * 50)
    from verifier import verify_findings
    artifacts = {"T1": "def f():\n    password = 'x'\n"}

    verified, quarantined = verify_findings([
        {"task": "T1", "level": "CRITICAL", "issue": "real",
         "evidence": "password = 'x'"},
        {"task": "T1", "level": "CRITICAL", "issue": "fabricated",
         "evidence": "except Exception:\n    pass"},
        {"task": "T1", "level": "MEDIUM", "issue": "no evidence"},
        {"task": "T1", "level": "OK", "issue": "无明显问题"},
    ], artifacts)

    assert [f["issue"] for f in verified] == ["real", "无明显问题"]
    assert [f["issue"] for f in quarantined] == ["fabricated", "no evidence"]
    assert quarantined[0]["quarantine_reason"] == "证据与代码不符"
    assert quarantined[1]["quarantine_reason"] == "证据缺失"
    print("  真证据过 / 伪证据隔 / 无证据隔 / OK 豁免")
    print("  [PASS]\n")


if __name__ == "__main__":
    print("\nHallucination defense tests\n")
    test_phantom_critical_quarantined_pipeline_done()
    test_real_findings_survive_verification()
    test_verifier_rules()
    print("=" * 50)
    print("全部通过!")
    print("=" * 50)
