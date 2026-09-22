# 已保存的实测证据

本目录的 7 个 JSON 文件保留原始字节；数据来自 2026-09-22、提交 e5bd01d8b76a23cc17b9a54de2cb2641298792fb 的评测。

- all_36_cases.json：逐题输入、标注、返回结果和时延。
- audited_metrics.json：独立复核指标。search 命中31/31，retrieve 命中28/31，两路径正确拒答均5/5。
- audit_upstream_summary.json：与逐题记录同轮次的原评测器汇总。
- upstream_summary.json：稍早 CLI 的汇总；时延不必与后续轮次相同。
- failure_scores.json：三条漏检目标章节低于0.08门槛的得分。
- sensitivity.json：两个Top-K配置与两个alpha配置的实验记录。
- environment.json：环境、提交号和源码校验值。

注意：原汇总的 failures 只统计 search；原 precision@3 按实际返回数作分母。正式口径见 [报告](../report.md)。

运行方法见 [目录说明](../README.md)，复核脚本为 [audit_rag.py](../audit_rag.py)。重跑结果请写入目录外，保留此处作为历史快照。
