"""
Day 11 fault-injection demo - PHASE 1: REPRODUCE an agent deadloop.

Scenario (the most common real-world deadloop shape): review-repair ping-pong.
- LeakyCoder always emits code with a hardcoded password (models an LLM
  whose "fix" never actually removes the flaw).
- Repair loop: CRITICAL finding -> route the task back to coder -> re-review.
- NO progress detection: the loop only ends when CRITICAL disappears,
  which never happens. Only the dumb maxTurns breakers can stop it.

Pre-run hypotheses (verify against the actual output):
  H1: reviewer's per-agent breaker fires first (maxTurns=3 < coder 5 < global 12)
  H2: it fires on reviewer's 4th run, at global tick 8
  H3: every cycle's CRITICAL findings are IDENTICAL - the loop spins with
      zero progress and has no way to notice
"""

from shared import Blackboard, MessageBus
from agents import CoderAgent, PlannerAgent, ReviewerAgent
from orchestrator import TeamOrchestrator

GLOBAL_MAX_TURNS = 12


class StubPlanner(PlannerAgent):
    """Planner stub: a single task, keeping the repro minimal."""

    def _simulate(self, feature):
        return [{"id": "T1", "desc": "implement login", "done": False}]


class LeakyCoder(CoderAgent):
    """Coder whose output always contains a hardcoded password.

    The repair attempt re-runs the same simulation, so the flaw survives
    every fix - exactly like an LLM that keeps "fixing" without effect.
    """

    def _simulate(self, task):
        return (
            f"# Task {task['id']}: {task['desc']}\n"
            f"PASSWORD = 'admin123'  # fix attempt: still here\n"
            f"def handle_{task['id'].lower()}():\n"
            f"    pass\n"
        )


def critical_signature(report):
    """CRITICAL lines of a review report, as a comparable tuple."""
    return tuple(sorted(line for line in report.splitlines() if "CRITICAL" in line))


def run_deadloop():
    print("=" * 60)
    print("PHASE 1: UNGUARDED review-repair loop (no progress detection)")
    print("=" * 60)

    cfg = {"api_key": ""}
    bb = Blackboard()
    bus = MessageBus()
    bb.write("tasks", [{"id": "T1", "desc": "implement login", "done": False}])

    coder = LeakyCoder(bb, bus, cfg)
    reviewer = ReviewerAgent(bb, bus, cfg)

    ticks = {"n": 0}

    def tick():
        ticks["n"] += 1
        if ticks["n"] > GLOBAL_MAX_TURNS:
            raise RuntimeError(
                f"全局轮次超限({GLOBAL_MAX_TURNS}) —— 疑似 Agent 间死循环")

    task = bb.read("tasks")[0]

    tick()
    coder.run(task)  # initial code (leaky from the start)

    signatures = []
    cycle = 0
    try:
        while True:
            cycle += 1
            tick()
            report = reviewer.run()
            signatures.append(critical_signature(report))
            print(f"  cycle {cycle}: critical findings = {signatures[-1]}")
            if not signatures[-1]:
                print("  no CRITICAL left -> loop ends normally")
                break
            tick()
            coder.run(task)  # repair attempt (ineffective by construction)
    except RuntimeError as e:
        print(f"\n  [BREAKER FIRED] {e}")

    print("\n" + "-" * 60)
    print("EVIDENCE SUMMARY")
    print("-" * 60)
    print(f"  global ticks consumed : {ticks['n']}/{GLOBAL_MAX_TURNS}")
    print(f"  coder turns used      : {coder.turns_used}/{coder.max_turns}")
    print(f"  reviewer turns used   : {reviewer.turns_used}/{reviewer.max_turns}")
    print(f"  review cycles done    : {len(signatures)}")
    distinct = len(set(signatures))
    print(f"  distinct findings sets: {distinct}  "
          f"({'IDENTICAL every cycle - zero progress' if distinct == 1 else 'changed'})")
    print(f"  wasted repair attempts: {coder.turns_used - 1} "
          f"(every one was guaranteed useless, and the loop could not tell)")


def run_guarded():
    print("=" * 60)
    print("PHASE 2: GUARDED orchestrator (no-progress detection active)")
    print("=" * 60)

    cfg = {"api_key": "", "global_max_turns": 12}

    # Same leaky coder, now inside the real orchestrator with the guard.
    team = TeamOrchestrator(cfg)
    team.planner = StubPlanner(team.bb, team.bus, cfg)
    team.coder = LeakyCoder(team.bb, team.bus, cfg)
    result = team.execute("实现登录功能")

    print("\n" + "-" * 60)
    print("GUARD SUMMARY")
    print("-" * 60)
    print(f"  status        : {result['status']}")
    print(f"  reason        : {result.get('reason', '-')}")
    print(f"  global turns  : {team.global_turns}/{GLOBAL_MAX_TURNS}")
    print(f"  coder turns   : {team.coder.turns_used}/{team.coder.max_turns}")
    print(f"  reviewer turns: {team.reviewer.turns_used}/{team.reviewer.max_turns}")
    print("  -> stopped by DIAGNOSIS (stalled repair), not by a blind breaker")


if __name__ == "__main__":
    run_deadloop()
    print()
    run_guarded()
