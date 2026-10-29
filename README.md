# dev-team-agent

多 Agent 软件开发团队模拟(Orchestrator-Worker 模式),带**分层故障防御**与**三类真实故障的注入-修复复盘**。Python 实现,离线可运行(无需 API Key)。

## 架构

```
feature_request ──► TeamOrchestrator(编排器,全局预算+修复回路)
                        │
        ┌───────────────┼────────────────┐
   PlannerAgent    CoderAgent      ReviewerAgent
   (拆解任务)      (生成代码)      (审查+证据锚定)
        └───── Blackboard(共享状态) + MessageBus(消息总线) ─────┘
```

## 分层防御(每一层都被故障注入实测验证过)

| 层 | 防什么 | 实现 |
|----|--------|------|
| L1 入口消毒 | Prompt 注入覆写载荷 | `security.py::InputSanitizer`(窄模式,配"忽略大小写"回归钉防误杀) |
| L2 产出不变量 | 空任务列表静默假成功 | 拆解为空 → 拒绝,failed |
| L3 证据锚定+交叉验证 | 幻觉发现(编造问题/编造引用) | `verifier.py`:发现必须携带命中行原文且为工件子串,未证实进隔离区 |
| L4 审查-修复回路+无进展检测 | 修复无效死循环 | CRITICAL 签名比对,连续 2 轮相同 → 带诊断终止 |
| L5 maxTurns 熔断 | 预算失控 | 单 Agent(2/5/3)+ 全局 12 轮 |

## 故障注入复盘(每篇含可复现 demo + 真实数据)

| 复盘 | 故障 | 一句话根因 |
|------|------|-----------|
| [retro-01](retro-01-deadloop.md) | 审查-修复乒乓死循环 | 回路缺第三种出口(无进展) |
| [retro-02](retro-02-prompt-injection.md) | 注入致静默假成功 | 信任边界在 prompt 里消失 |
| [retro-03](retro-03-hallucination.md) | 幻觉 CRITICAL 劫持管线 | 结论没有证据锚点 |

## 运行与测试

```bash
python test_offline.py        # 基础流程 5 项
python test_repair_loop.py    # 修复回路守卫 2 项
python test_security.py       # 注入防御 3 项
python test_hallucination.py  # 幻觉防御 3 项
python deadloop_demo.py       # 故障复现 demo(两阶段对照)
python injection_demo.py
python hallucination_demo.py
```

全部 13 项测试离线可跑;在线模式设置 `api_key` 后走真实 LLM。

## 设计说明

- **确定性替身方法论**:demo 中的 `LeakyCoder`/`ConfusedPlanner`/`HallucinatingReviewer` 确定性建模"LLM 屈服/幻觉"行为,使故障离线可复现、可测试(真实 LLM 是否屈服是概率性的——这正是需要评估统计的原因)
- **测试成对原则**:每个"拦东西"的机制配一个"不许拦错"的回归钉;本项目中回归钉两次抓住防御代码自身的 bug
