# RailMind RAG 检索评测与可视化

本目录包含对固定版本的检索复测、指标口径复核、失败分析和六组可视化；不修改线上检索实现或原项目自动生成报告。

**阅读入口：[图文评测报告](report.md)** · [离线 HTML](report.html)（下载后用浏览器打开）

## 结果摘要

评测提交：`e5bd01d8b76a23cc17b9a54de2cb2641298792fb`；评测日期：2026-09-22；Top-K=3，α=0.55。

| 指标 | search | retrieve |
| --- | ---: | ---: |
| 可答题命中 | 31/31 | 28/31 |
| 首位命中 | 29/31 | 15/31 |
| MRR@3 | 0.9677 | 0.6774 |
| 标准 P@3（固定分母） | 0.3548 | 0.3118 |
| 正确拒答 | 5/5 | 5/5 |

数据为26条内置演示知识块上的开发回归集，不是独立测试集、正式铁路规程验证或生成答案准确率。关键词路径保留LS-03、CB-03、CB-04三条漏检。

## 目录

| 路径 | 内容 |
| --- | --- |
| [report.md](report.md) | GitHub可直接阅读的图文报告 |
| [report.html](report.html) | 自包含离线展示版，图表内嵌 |
| [figures/](figures/) | 6张220 DPI PNG和6张SVG |
| [evidence/](evidence/) | 原始逐题数据、汇总、参数结果和环境 |
| [audit_rag.py](audit_rag.py) | 调用原检索器，补充独立统计；不改变检索算法 |
| [generate_visuals.py](generate_visuals.py) | 从固定快照重新生成图表和报告 |
| [source_report.md](source_report.md) | 图文报告的基础文本来源 |
| [chart_manifest.json](chart_manifest.json) | 图表说明和源JSON校验值 |

## 重跑评测

在已具备RailMind依赖的Python环境中，从仓库根目录执行：

```bash
git worktree add --detach ../RailMind-eval-e5bd01d e5bd01d8b76a23cc17b9a54de2cb2641298792fb
python docs/rag-eval/audit_rag.py --repo ../RailMind-eval-e5bd01d --out ../railmind-rag-rerun
```

工作目录用于固定被测源码，本PR中的脚本仍从当前仓库调用。若上述工作目录已建立，可直接执行第二条。所有新数据写入 `../railmind-rag-rerun`，不覆盖本目录历史快照。

若只希望评测当前检出的源码，可使用 `--repo .`；该结果代表当前版本，不应直接冒充本报告的固定版本结果。具体版本以新输出的environment.json为准。

原实测环境为Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、scikit-learn 1.8.0；其余项目依赖以仓库requirements.txt为准。不同机器的耗时会变化。

## 重新绘图

仅阅读报告无需安装绘图依赖。作图需要matplotlib、NumPy、pandoc和一份中文字体。仓库根目录运行：

```bash
python docs/rag-eval/generate_visuals.py --font /path/to/NotoSansCJKsc-Regular.otf
```

Windows可将字体参数换为本机中文字体文件路径，例如 `C:/Windows/Fonts/msyh.ttc`。PNG和SVG已随目录提交，不需要为看图重新运行。

脚本只用于保存的固定快照，默认读取同目录source_report.md、evidence和chart_manifest.json，生成report.md、report.html及figures。发现输入数据变化会报错，避免把新结果与固定说明混在一起。用于新实验时应先同步审核图题、统计口径和报告文字。

## 图表与口径

- 总体指标、首个相关结果排名、领域热图、失败章节门槛、参数敏感性、Precision分母比较。
- 标准P@3固定除以3；原报告按返回数计算的口径另列。
- 31条可答题共33个问题—相关章节关系，当前标注且结果不重复时，标准P@3上限为33/(31×3)=0.3548。
- 图表标注与原始JSON配套；新运行不要直接覆盖已提交证据。

本目录只补充评测材料。原评测器的指标命名、双路径失败汇总等代码问题在报告中说明，未在此提交中修改。
