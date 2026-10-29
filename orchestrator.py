"""
编排器 - 对应知识点: Orchestrator-Worker 模式 + Human-in-the-Loop + 失败处理

这是多 Agent 系统的「大脑」。它不自己干活，而是：
1. 调 Planner 拆解需求
2. 把每个任务分派给 Coder（主控-执行者）
3. 调 Reviewer 审查
4. 关键节点 Human-in-the-Loop 把关
5. 全局 maxTurns + 失败处理

整个 run() 就是宏观 ReAct: Observe→Think→Act→Observe→输出
"""

from shared import Blackboard, MessageBus
from agents import PlannerAgent, CoderAgent, ReviewerAgent
from security import InputSanitizer


class TeamOrchestrator:
    """软件开发团队的编排器（项目经理角色）。"""

    # No-progress guard: identical CRITICAL findings across this many
    # repair cycles mean the repair is ineffective - abort with a
    # diagnosis instead of burning turns until a dumb breaker fires.
    MAX_STALLED_REPAIRS = 2

    def __init__(self, config):
        self.config = config
        self.bb = Blackboard()
        self.bus = MessageBus()
        self.sanitizer = InputSanitizer()
        self.global_turns = 0
        self.max_turns = config.get("global_max_turns", 12)

        self.planner = PlannerAgent(self.bb, self.bus, config)
        self.coder = CoderAgent(self.bb, self.bus, config)
        self.reviewer = ReviewerAgent(self.bb, self.bus, config)

    def execute(self, feature_request):
        print(f"\n{'='*50}")
        print(f"[需求] {feature_request}")
        print(f"{'='*50}")

        # Layer 1: boundary defense - untrusted input is screened before
        # it ever reaches a prompt. Rejected inputs never become instructions.
        violation = self.sanitizer.check(feature_request)
        if violation:
            self.bb.write("status", "rejected")
            reason = f"输入疑似提示注入({violation}) —— 已在入口拒绝"
            print(f"\n流程中断: {reason}")
            self.bus.send("orchestrator", "human", f"流程拒绝: {reason}", "alert")
            return {"status": "failed", "reason": reason, "snapshot": self.bb.snapshot()}

        self.bb.write("feature_request", feature_request)
        self.bb.write("status", "planning")

        try:
            self._tick()
            tasks = self.planner.run(feature_request)
            # Layer 2: output invariant - zero tasks is never a success,
            # no matter whether the cause is injection or planner failure.
            if not tasks:
                raise RuntimeError("拆解结果为空任务列表 —— 拒绝静默成功(疑似注入或规划失败)")
            self.bus.send("orchestrator", "coder", f"共 {len(tasks)} 个任务待实现", "task")

            self.bb.write("status", "coding")
            for task in tasks:
                self._tick()
                self.coder.run(task)

            self.bb.write("status", "reviewing")
            self._tick()
            report = self.reviewer.run()
            report = self._review_and_repair(report)

            self._check_human_approval()

            self.bb.write("status", "done")
            return self._finalize(report)

        except RuntimeError as e:
            self.bb.write("status", "failed")
            print(f"\n流程中断: {e}")
            self.bus.send("orchestrator", "human", f"流程失败: {e}", "alert")
            return {"status": "failed", "reason": str(e), "snapshot": self.bb.snapshot()}

    def _tick(self):
        """全局轮次计数 —— 防止整个系统失控（多 Agent 成本爆炸的核心防线）"""
        self.global_turns += 1
        if self.global_turns > self.max_turns:
            raise RuntimeError(f"全局轮次超限({self.max_turns}) —— 疑似 Agent 间死循环")

    @staticmethod
    def _critical_tasks(report):
        """Task ids mentioned in CRITICAL lines of a review report."""
        tasks = []
        for line in report.splitlines():
            if "CRITICAL" in line:
                body = line.split("]", 1)[1].strip()  # "- [CRITICAL] T1: xx" -> "T1: xx"
                tasks.append(body.split(":", 1)[0].strip())
        return tuple(sorted(set(tasks)))

    def _review_and_repair(self, report):
        """修复回路（含无进展检测）。

        CRITICAL 问题路由回 coder 重做 -> 复审，直到:
        a) CRITICAL 清零（正常出口）
        b) 连续 MAX_STALLED_REPAIRS 轮发现完全相同 -> 修复无效，
           抛出带诊断的 RuntimeError（这是熔断给不出的信息）
        c) 预算熔断兜底（不变）
        """
        stalled = 0
        signature = self._critical_tasks(report)
        tasks_by_id = {t["id"]: t for t in self.bb.read("tasks")}
        while signature:
            if stalled >= self.MAX_STALLED_REPAIRS:
                raise RuntimeError(
                    f"修复无进展: {', '.join(signature)} 在 {stalled} 轮修复后仍存在"
                    f" —— 停止循环, 转人工处理")
            self._tick()
            for task_id in signature:
                self.coder.run(tasks_by_id[task_id])
            self._tick()
            report = self.reviewer.run()
            new_signature = self._critical_tasks(report)
            stalled = stalled + 1 if new_signature == signature else 0
            signature = new_signature
        return report

    def _check_human_approval(self):
        """Human-in-the-Loop: 检查是否有需人工确认的事项"""
        approvals = self.bus.receive("human")
        if approvals:
            print(f"\n待人工确认 ({len(approvals)} 项):")
            for a in approvals:
                print(f"   - {a['content']}")
            print("   （模拟环境自动放行；生产环境应暂停等待真人确认）")

    def _finalize(self, report):
        snap = self.bb.snapshot()
        print(f"\n{'='*50}")
        print(f"团队协作完成!")
        print(f"{'='*50}")
        print(f"  任务: {snap['tasks_done']}/{snap['tasks_total']} 完成")
        print(f"  代码: {snap['code_count']} 份")
        print(f"  审查: {snap['reviews']} 份报告")
        print(f"  全局轮次: {self.global_turns}/{self.max_turns}")
        print(f"\n{report}")
        return {"status": "done", "snapshot": snap, "report": report, "global_turns": self.global_turns}
