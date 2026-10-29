"""
Agent 角色层 - 对应知识点: Agent-as-a-Service + Tool Use + ReAct

设计要点：
- BaseAgent 抽象基类：所有角色共享统一接口 → 可替换、Model-Agnostic
- 三个角色各是一个独立小 Agent（各有自己的 ReAct + maxTurns）
- 离线模式用模拟响应；在线模式调真实 Claude
"""

import json
from abc import ABC, abstractmethod
from shared import Blackboard, MessageBus
from verifier import verify_findings


class BaseAgent(ABC):
    """所有 Agent 的基类。统一接口让 Orchestrator 以同样方式调度任何角色。"""

    def __init__(self, name, role, blackboard, bus, config, max_turns=3):
        self.name = name
        self.role = role
        self.bb = blackboard
        self.bus = bus
        self.config = config
        self.max_turns = max_turns
        self.turns_used = 0

    @abstractmethod
    def run(self, task_input):
        pass

    def _check_turns(self):
        """maxTurns 安全阀 —— 防止单个 Agent 烧光预算"""
        self.turns_used += 1
        if self.turns_used > self.max_turns:
            raise RuntimeError(f"[{self.name}] 超过 maxTurns({self.max_turns})，强制停止")

    def announce(self, msg):
        print(f"  [{self.role}] {msg}")
        self.bus.send(self.name, "orchestrator", msg, msg_type="info")


class PlannerAgent(BaseAgent):
    """规划者：把功能需求拆解成可执行任务列表。"""

    def __init__(self, blackboard, bus, config):
        super().__init__("planner", "规划者", blackboard, bus, config, max_turns=2)

    def run(self, feature_request):
        self._check_turns()
        self.announce(f"收到需求: {feature_request}")

        tasks = self._call_llm(feature_request) if self.config.get("api_key") else self._simulate(feature_request)

        self.bb.write("tasks", tasks)
        self.announce(f"拆解出 {len(tasks)} 个任务")
        return tasks

    def _simulate(self, feature):
        return [
            {"id": "T1", "desc": "定义数据模型", "done": False},
            {"id": "T2", "desc": "实现核心逻辑", "done": False},
            {"id": "T3", "desc": "添加错误处理", "done": False},
            {"id": "T4", "desc": "编写基础测试", "done": False},
        ]

    def _call_llm(self, feature):
        import anthropic
        client = anthropic.Anthropic(api_key=self.config["api_key"])
        resp = client.messages.create(
            model=self.config["planner_model"],
            max_tokens=1024,
            messages=[{"role": "user", "content": f"拆成3-5个开发任务，返回JSON数组: {feature}"}],
        )
        return json.loads(resp.content[0].text)


class CoderAgent(BaseAgent):
    """编码者：把任务变成代码。"""

    def __init__(self, blackboard, bus, config):
        super().__init__("coder", "编码者", blackboard, bus, config, max_turns=5)

    def run(self, task):
        self._check_turns()
        self.announce(f"实现任务 {task['id']}: {task['desc']}")

        code = self._call_llm(task) if self.config.get("api_key") else self._simulate(task)

        artifacts = self.bb.read("code_artifacts")
        artifacts[task["id"]] = code
        self.bb.write("code_artifacts", artifacts)
        task["done"] = True
        self.announce(f"任务 {task['id']} 完成 ({len(code)} 字符)")
        return code

    def _simulate(self, task):
        return (
            f"# Task {task['id']}: {task['desc']}\n"
            f"def handle_{task['id'].lower()}():\n"
            f'    """实现: {task['desc']}"""\n'
            f"    pass  # TODO: implement\n"
        )

    def _call_llm(self, task):
        import anthropic
        client = anthropic.Anthropic(api_key=self.config["api_key"])
        resp = client.messages.create(
            model=self.config["coder_model"],
            max_tokens=2048,
            messages=[{"role": "user", "content": f"用 Python 实现这个任务，只返回代码: {task['desc']}"}],
        )
        return resp.content[0].text


class ReviewerAgent(BaseAgent):
    """
    审查者：审查所有代码，产出报告。
    集成 Code Review 知识：严重性分级 + 安全检查 + Human-in-the-Loop。
    """

    def __init__(self, blackboard, bus, config):
        super().__init__("reviewer", "审查者", blackboard, bus, config, max_turns=3)

    def run(self, _=None):
        self._check_turns()
        artifacts = self.bb.read("code_artifacts")
        self.announce(f"开始审查 {len(artifacts)} 份代码")

        findings = []
        for task_id, code in artifacts.items():
            findings.extend(self._scan_code(task_id, code))

        # Knowledge-base cross-validation: findings are only confirmed
        # when their evidence exists in the artifact. Hallucinated
        # findings go to quarantine - visible, but never routed onward.
        verified, quarantined = verify_findings(findings, artifacts)

        report = self._build_report(verified, quarantined)
        self.bb.append("review_reports", report)

        critical = [f for f in verified if f["level"] == "CRITICAL"]
        if critical:
            self.announce(f"[警告] 发现 {len(critical)} 个 CRITICAL 问题，需人工确认!")
            self.bus.send(self.name, "human", "CRITICAL issues need approval", "approval")
        if quarantined:
            self.announce(f"[隔离] {len(quarantined)} 条发现证据不符，已隔离待查")
        return report

    @staticmethod
    def _line_with(code, needle, case_sensitive=True):
        """First stripped line containing needle ('' if absent) - the evidence."""
        for line in code.splitlines():
            haystack = line if case_sensitive else line.lower()
            needle_cmp = needle if case_sensitive else needle.lower()
            if needle_cmp in haystack:
                return line.strip()
        return ""

    def _scan_code(self, task_id, code):
        """Scan one artifact. Real findings cite an evidence line so the
        verifier can cross-check them against the artifact later."""
        findings = []
        seen_issues = set()
        for needle, level, issue, ci in [
            ("password", "CRITICAL", "疑似硬编码密钥", True),
            ("secret", "CRITICAL", "疑似硬编码密钥", True),
            ("except:", "MEDIUM", "空 except 吞错误", False),
            ("except pass", "MEDIUM", "空 except 吞错误", False),
            ("TODO", "LOW", "未完成的 TODO", True),
        ]:
            if issue in seen_issues:
                continue
            evidence = self._line_with(code, needle, case_sensitive=not ci)
            if evidence:
                findings.append({
                    "task": task_id, "level": level, "issue": issue,
                    "evidence": evidence,
                })
                seen_issues.add(issue)
        if not findings:
            findings.append({"task": task_id, "level": "OK", "issue": "无明显问题"})
        return findings

    def _build_report(self, findings, quarantined=()):
        lines = ["## 代码审查报告", ""]
        for f in findings:
            lines.append(f"- [{f['level']}] {f['task']}: {f['issue']}")
        if quarantined:
            lines += ["", "## 未经证实(已隔离)"]
            for f in quarantined:
                lines.append(
                    f"- [隔离] {f['task']}: {f['issue']} ({f['quarantine_reason']})")
        return "\n".join(lines)
