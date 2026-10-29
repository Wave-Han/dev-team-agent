"""
Day 13 fault-injection demo - PHASE 1: hallucinated review findings.

Scenario: an LLM reviewer invents plausible-sounding issues that do not
exist in the code. Real-world mechanism: "review this code" prompts
carry the prior "reviews find problems"; on mostly-clean code the model
sometimes satisfies that expectation by INVENTING issues - and even
fabricating plausible-looking evidence snippets.

Offline stand-in: HallucinatingReviewer deterministically adds two
invented findings, each with a FABRICATED evidence snippet that is not
in the artifact (models citation fabrication too).

Pre-run hypotheses:
  H1: invented findings enter the report unchecked - findings carry
      conclusions, not evidence, so nothing can tell real from fake
  H2: an invented CRITICAL triggers the Day-11 repair loop -> coder
      "fixes" a phantom -> reviewer hallucinates again -> no-progress
      guard fires -> THE PIPELINE FAILS ON A PROBLEM THAT DOES NOT EXIST
  H3: eval-metric view: 3 findings, 1 real, 2 hallucinated -> P = 33%
"""

from agents import ReviewerAgent
from deadloop_demo import StubPlanner
from orchestrator import TeamOrchestrator


class HallucinatingReviewer(ReviewerAgent):
    """Stand-in reviewer that invents findings with fabricated evidence."""

    INVENTED = [
        {"level": "MEDIUM", "issue": "空 except 吞错误",
         "evidence": "except Exception:\n    pass"},
        {"level": "CRITICAL", "issue": "SQL 注入风险",
         "evidence": "sql = \"SELECT * FROM t WHERE id=\" + id"},
    ]

    def _scan_code(self, task_id, code):
        findings = super()._scan_code(task_id, code)
        for f in self.INVENTED:
            findings.append({**f, "task": task_id})
        return findings


def phantom_failure_through_pipeline():
    print("=" * 60)
    print("H2: invented CRITICAL hijacks the repair loop")
    print("=" * 60)
    cfg = {"api_key": "", "global_max_turns": 12}
    team = TeamOrchestrator(cfg)
    team.planner = StubPlanner(team.bb, team.bus, cfg)
    team.reviewer = HallucinatingReviewer(team.bb, team.bus, cfg)
    result = team.execute("实现登录功能")

    print("\n  -> status:", result["status"])
    print("  -> reason:", result.get("reason", "-"))
    print("  -> turns :", f"global={team.global_turns}/12")
    print("  -> the artifact NEVER contained a CRITICAL problem;")
    print("     the pipeline failed on a PHANTOM (H2 confirmed)"
          if result["status"] == "failed" else "  -> defended")


def precision_view():
    print()
    print("=" * 60)
    print("H3: eval-metric view of the same hallucination")
    print("=" * 60)
    code = "# Task T1: implement login\ndef handle_t1():\n    pass  # TODO: implement\n"
    reviewer = HallucinatingReviewer.__new__(HallucinatingReviewer)
    findings = HallucinatingReviewer._scan_code(reviewer, "T1", code)
    print(f"  artifact : {code!r}")
    print(f"  findings : {[f['issue'] for f in findings]}")
    real = sum(1 for f in findings if not f.get("fabricated", False) and f["issue"] == "未完成的 TODO")
    print(f"  real: {real}/{len(findings)} -> if fed to the eval confusion")
    print(f"  matrix: TP={real}, FP={len(findings)-real} -> Precision = "
          f"{real}/{len(findings)} = {real/len(findings):.0%}")
    print("  -> hallucination IS the LLM flavor of a false positive (H3)")


def phase2_guarded():
    print()
    print("=" * 60)
    print("PHASE 2: GUARDED (evidence anchoring + cross-validation)")
    print("=" * 60)
    cfg = {"api_key": "", "global_max_turns": 12}
    team = TeamOrchestrator(cfg)
    team.planner = StubPlanner(team.bb, team.bus, cfg)
    team.reviewer = HallucinatingReviewer(team.bb, team.bus, cfg)
    result = team.execute("实现登录功能")

    print("\n  -> status:", result["status"], f"(turns={team.global_turns}/12, no phantom repair)")
    print("  -> final report:")
    for line in result["report"].splitlines():
        if line.strip():
            print("     ", line)
    print("\n  -> 3 findings scanned: 1 real (confirmed), 2 invented (quarantined)")
    print("     precision of CONFIRMED report: 1/1 = 100% (was 33% unguarded)")


if __name__ == "__main__":
    print("########## PHASE 1: unguarded ##########")
    phantom_failure_through_pipeline()
    precision_view()
    phase2_guarded()
