"""Build RailMind charts and self-contained HTML from saved audit evidence.
Requires matplotlib, numpy, pandoc and a Chinese font supplied with --font.
"""
from pathlib import Path
import argparse, base64, hashlib, html, json, re, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

p=argparse.ArgumentParser()
p.add_argument('--font', required=True)
p.add_argument('--report', default=str(Path(__file__).resolve().with_name('source_report.md')))
p.add_argument('--root', default=str(Path(__file__).resolve().parent))
a=p.parse_args();root=Path(a.root).resolve();ev=root/'evidence';figdir=root/'figures';figdir.mkdir(exist_ok=True)
font_manager.fontManager.addfont(a.font)
fontname=font_manager.FontProperties(fname=a.font).get_name()
plt.rcParams.update({'font.family':fontname,'font.size':12,'axes.unicode_minus':False,'svg.fonttype':'path', 'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False,'axes.labelcolor':'#475569','xtick.color':'#64748b','ytick.color':'#334155','figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
D=json.loads((ev/'audited_metrics.json').read_text());S=json.loads((ev/'sensitivity.json').read_text());F=json.loads((ev/'failure_scores.json').read_text());C=json.loads((ev/'all_36_cases.json').read_text());E=json.loads((ev/'environment.json').read_text())
# This renderer contains narrative labels for the recorded benchmark snapshot.
# Reject changed input data instead of silently combining new scores and old claims.
expected_commit = 'e5bd01d8b76a23cc17b9a54de2cb2641298792fb'
if E['commit'] != expected_commit or len(C) != 36:
    raise ValueError('This renderer is for the recorded 36-case snapshot only; review narrative labels before using new data.')
manifest_path = root / 'chart_manifest.json'
if manifest_path.exists():
    saved_manifest = json.loads(manifest_path.read_text())
    for name, expected_hash in saved_manifest['source_files'].items():
        if hashlib.sha256((ev / name).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f'Evidence changed: {name}. Review narrative labels before plotting new results.')

BLUE='#2463A6';TEAL='#09847E';INK='#152F49';MUTED='#60758B';AMBER='#C26B2E';LIGHT='#E7EEF5'
paths=['search','retrieve'];labels=['自然语言 search','关键词 retrieve'];cols=[BLUE,TEAL]
manifest=[]
def save(fig,name,title,caption):
    fig.savefig(figdir/(name+'.png'),dpi=220,bbox_inches='tight',pad_inches=.25)
    fig.savefig(figdir/(name+'.svg'),bbox_inches='tight',pad_inches=.25)
    plt.close(fig)
    manifest.append({'name':name,'title':title,'caption':caption})
def grid(ax,axis='x'):
    ax.set_axisbelow(True);ax.grid(axis=axis,color=LIGHT,linewidth=.8);ax.tick_params(length=0,pad=9)
def head(fig,title,sub):
    fig.text(.035,.965,title,ha='left',va='top',fontsize=20,color=INK,weight='bold')
    fig.text(.035,.885,sub,ha='left',va='top',fontsize=11,color=MUTED)

# 01: overview with fixed range and separate metric definitions.
fig,ax=plt.subplots(figsize=(11,6));fig.subplots_adjust(top=.74,left=.18,right=.91,bottom=.11)
keys=['hit','mrr','recall','ndcg','precision_fixed_k'];names=['Hit@3','MRR@3','Recall@3','NDCG@3','标准 P@3']
y=np.arange(len(keys))
for j,path in enumerate(paths):
    yy=y+(-.18 if j==0 else .18);v=[D[path][k] for k in keys]
    ax.barh(yy,v,height=.27,color=cols[j],label=labels[j],zorder=3)
    for yi,val in zip(yy,v):ax.text(val+.014,yi,f'{val:.4f}',va='center',fontsize=10,color=cols[j])
ax.set(yticks=y,yticklabels=names,xlim=(0,1.12),xticks=np.linspace(0,1,6));ax.invert_yaxis();grid(ax)
ax.legend(loc='lower left',bbox_to_anchor=(0,1.025),ncol=2,frameon=False,fontsize=11)
head(fig,'01  双路径效果：命中之外，还要看排序','31 条可答样本 · Top-K=3 · α=0.55 · 均为同一回归集，不同查询输入')
save(fig,'01_metrics','双路径检索质量对比','自然语言路径使用原问题，关键词路径使用预给关键词；差距不能全部归因于检索算法。P@3 固定除以 3，其解释见图 06。')

# 02: first relevant rank distribution, exact additive counts.
fig,ax=plt.subplots(figsize=(11,4.5));fig.subplots_adjust(top=.64,left=.2,right=.95,bottom=.13)
rkeys=['1','2','3','None'];rlabels=['首位命中','第 2 位命中','第 3 位命中','Top-3 未命中'];rc=[BLUE,'#6BA2C4','#BDD4E3',AMBER]
left=np.zeros(2)
for k,lab,color in zip(rkeys,rlabels,rc):
    vals=np.array([D[path]['rank_counts'].get(k,0) for path in paths]);ax.barh([0,1],vals,left=left,height=.5,color=color,label=lab)
    for i,v in enumerate(vals):
        if v:ax.text(left[i]+v/2,i,str(v),ha='center',va='center',color='white' if k in ['1','None'] else INK,fontsize=14,weight='bold')
    left+=vals
ax.set(yticks=[0,1],yticklabels=labels,xlim=(0,31),xticks=[0,5,10,15,20,25,31],xlabel='用例数（每条路径 n=31）');ax.invert_yaxis();grid(ax)
ax.legend(loc='lower left',bbox_to_anchor=(-.015,1.06),ncol=4,frameon=False,fontsize=10)
head(fig,'02  首位命中率的差距，比 Top-3 更明显','search：29/31（93.5%）  ·  retrieve：15/31（48.4%）  ·  相差 14 题')
save(fig,'02_ranks','首个相关结果的位置分布','关键词路径有 13 题到第 2 或第 3 位才出现相关依据，另有 3 题未命中。若后续回答优先使用首条引用，排序问题值得单独检查；此处未测试生成答案。')

# 03: domain heatmap, explicit n and no fabricated trends.
doms=['composite_structure','pantograph','underbody','lineside','cabin','general'];dn=['复合材料结构','受电弓','车底检查门','线路侧','车厢巡检','通用跨域']
data=np.array([[D['by_domain'][d][p][m] for p in paths for m in ['hit','mrr']] for d in doms])
fig,ax=plt.subplots(figsize=(11,6.4));fig.subplots_adjust(top=.77,left=.23,right=.86,bottom=.11)
cmap=LinearSegmentedColormap.from_list('railmind',['#F2F6FA','#A1C2D8','#2463A6'])
im=ax.imshow(data,vmin=0,vmax=1,cmap=cmap,aspect='auto')
ax.set(xticks=range(4),xticklabels=['search\nHit@3','search\nMRR@3','retrieve\nHit@3','retrieve\nMRR@3'],yticks=range(6),yticklabels=[f'{n}  n={D["by_domain"][d]["search"]["answerable"]}' for d,n in zip(doms,dn)])
ax.tick_params(length=0,pad=12);ax.axvline(1.5,color='white',lw=5)
for i in range(6):
    for j in range(4):ax.text(j,i,f'{data[i,j]:.4f}',ha='center',va='center',color='white' if data[i,j]>.72 else INK,fontsize=12)
for i in range(5):ax.axhline(i+.5,color='white',lw=3)
cb=fig.colorbar(im,ax=ax,fraction=.035,pad=.04);cb.outline.set_visible(False);cb.set_ticks([0,.5,1])
head(fig,'03  漏检集中在车厢巡检与线路侧','关键词路径：车厢巡检 4/6 命中；线路侧 6/7 命中。各领域样本量较小。')
save(fig,'03_domains','领域表现矩阵','通用跨域只有 1 题，满分不等于充分验证。热图统一使用 0～1 色阶；格内数值与原始逐题统计一致。')

# 04: relevance scores against the actual filter threshold.
fig,ax=plt.subplots(figsize=(11,4.8));fig.subplots_adjust(top=.73,left=.26,right=.91,bottom=.15)
v=[f['tfidf_cosine'] for f in F];yy=np.arange(3)
ax.barh(yy,v,height=.45,color=AMBER)
for i,val in enumerate(v):ax.text(val+.002,i,f'{val:.4f}',va='center',color=AMBER,fontsize=12)
ax.axvline(.08,color=INK,ls='--',lw=1.5,label='现有过滤门槛 0.0800')
ax.set(yticks=yy,yticklabels=['LS-03  大风巡检','CB-03  倒地时长','CB-04  通道堵塞'],xlim=(0,.1),xticks=np.arange(0,.101,.02),xlabel='目标章节的 TF-IDF 余弦分数（不是置信概率）');ax.invert_yaxis();grid(ax)
ax.legend(loc='lower right',bbox_to_anchor=(1,1.005),frameon=False,fontsize=11)
head(fig,'04  目标章节在排序前已被过滤','3 条漏检并非“排在第 4、5 位”；泛化关键词使目标章节分数低于 0.08。')
save(fig,'04_failures','失败用例的门槛分析','相关章节被提前移除，所以扩大 Top-K 无法恢复它们。下一步应补充天气、倒地、堵塞等查询信息，并联合验证误召回，不能据此直接统一降低门槛。')

# 05: parameter sensitivity; true numeric x scale, no extrapolation.
fig,axs=plt.subplots(2,2,figsize=(11,8.3));fig.subplots_adjust(top=.78,left=.09,right=.94,bottom=.09,hspace=.5,wspace=.28)
configs_k=sorted([r for r in S if r['top_k']!=3]+[{'top_k':3,'alpha':.55,**{p:D[p] for p in paths}}],key=lambda x:x['top_k'])
configs_a=sorted([r for r in S if r['top_k']==3]+[{'top_k':3,'alpha':.55,**{p:D[p] for p in paths}}],key=lambda x:x['alpha'])
for col,configs,xkey,xlabel in [(0,configs_k,'top_k','Top-K（α=0.55）'),(1,configs_a,'alpha','α（Top-K=3）')]:
    for row,metric in enumerate(['hit','mrr']):
        ax=axs[row,col]
        for pi,path in enumerate(paths):
            x=[r[xkey] for r in configs];ys=[r[path][metric] for r in configs]
            ax.plot(x,ys,marker='o' if pi==0 else 's',color=cols[pi],linewidth=2,ms=6,label=labels[pi])
            for xx,yv in zip(x,ys):ax.annotate(f'{yv:.3f}',(xx,yv),textcoords='offset points',xytext=(0,8 if pi==0 else -17),ha='center',fontsize=9,color=cols[pi])
        ax.set_ylim(0,1.12);ax.set_yticks([0,.25,.5,.75,1]);ax.set_xticks([r[xkey] for r in configs]);ax.set_xlabel(xlabel);ax.set_ylabel(('Hit@' if metric=='hit' else 'MRR@')+('K' if col==0 else '3'));grid(ax,'y')
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper left',bbox_to_anchor=(.07,.845),ncol=2,frameon=False,fontsize=11)
head(fig,'05  扩大 Top-K 未补回漏检，默认权重仍需验证','只改变一个参数；保留查询扩展与 TF-IDF 门槛。各折线仅连接已测配置，不代表连续区间实测。')
save(fig,'05_sensitivity','Top-K 与权重敏感性','Top-K 从 3 增至 5，命中与排序指标均未改善。关键词路径 α=1 的 MRR@3 为 0.7204，高于默认 0.6774；这是回归集观察，不能据此宣布独立测试最优。')

# 06: precision denominator, explicit attainable ceiling under fixed gold labels.
ceiling=sum(min(len(r['case']['relevant']),3)/3 for r in C if not r['case']['should_refuse'])/31
fig,axs=plt.subplots(1,2,figsize=(11,5.2));fig.subplots_adjust(top=.69,left=.065,right=.94,bottom=.16,wspace=.32)
for ax,key,title in zip(axs,['precision_fixed_k','precision_returned'],['标准 P@3：固定除以 3','实际返回精确率：除以返回条数']):
    vals=[D[p][key] for p in paths];ax.bar([0,1],vals,width=.48,color=cols)
    for x,val in enumerate(vals):ax.text(x,val+.025,f'{val:.4f}',ha='center',color=cols[x],fontsize=13,weight='bold',bbox=dict(facecolor='white',edgecolor='none',pad=1.5))
    ax.set(xticks=[0,1],xticklabels=['search','retrieve'],ylim=(0,1),yticks=[0,.25,.5,.75,1],title=title);grid(ax,'y')
axs[0].axhline(ceiling,color=MUTED,ls='--',lw=1.2);axs[0].text(.5,.74,f'当前标注下的理论上限\n33 ÷ (31 × 3) = {ceiling:.4f}',transform=axs[0].transAxes,ha='center',fontsize=11,color=MUTED)
head(fig,'06  同名 Precision，不同分母会改变解释','29 题标注 1 个相关章节，2 题标注 2 个；共 33 个“问题—相关章节”关系。')
save(fig,'06_precision','精确率口径与标注密度','自然语言路径已召回全部标注相关章节，因此标准 P@3 达到当前标注下的理论上限。实际返回精确率仍低于 1，说明返回列表中还包含未被标为相关的内容；两种口径应并列说明。')

# Build a portable Markdown version. All original content is retained.
source=Path(a.report).read_text()
source=source.replace('# RailMind RAG 检索效果评测报告','# RailMind RAG 检索效果评测报告 · 图文增强版',1)
lookup={m['name']:m for m in manifest}
def figmd(name):
    m=lookup[name]
    return f'\n\n![{m["title"]}](figures/{name}.png)\n\n**图 {name[:2]}｜{m["title"]}。** {m["caption"]}\n\n'
insertions=[('### 5.1 默认配置总体结果','01_metrics'),('### 5.2 分领域结果','03_domains'),('## 六、失败用例与原因分析','04_failures'),('## 七、参数敏感性实验','05_sensitivity')]
for marker,name in insertions:source=source.replace(marker,marker+figmd(name),1)
marker='### 5.2 分领域结果';source=source.replace(marker,figmd('02_ranks')+marker,1)
source=source.replace('## 八、证据边界与后续工作','### 7.3 补充分析：标注密度与精确率解释'+figmd('06_precision')+'## 八、证据边界与后续工作',1)
summary='''## 结果速览与新增分析

> **结论范围：** 26 条内置演示知识块，36 条开发回归用例；本次只复用已保存的真实实测结果作图，没有新增或改写实验数值。

| 关键观察 | 数据依据 | 对比赛汇报的含义 |
| --- | --- | --- |
| 自然语言检索能找到预期依据 | Hit@3=31/31；首位命中29/31 | 说明当前回归集可用，不能代表真实规程问答准确率 |
| 关键词路径存在排序与漏检问题 | Hit@3=28/31；首位命中15/31 | 应同时关注“是否找到”和“是否排在首位” |
| 3条漏检均被门槛提前过滤 | 目标章节分数0.0551或0.0581，门槛0.08 | 优先保留查询中的具体场景信息 |
| 标准P@3受标注密度限制 | 共33个问题—相关章节关系，理论上限0.3548 | 不应将P@3较低单独解释为检索失败 |
| 拒答验证样本仍少 | 两路径均5/5正确拒答 | 只能陈述这5条已测样本通过 |

**新增分析说明。** 自然语言与关键词路径的首位命中率相差约45.2个百分点，比Hit@3的9.7个百分点差距更大；这提示排序质量应单独评测。两路径的输入信息量不同，上述差距不能解释为单一算法因素的因果效应。

'''
source=source.replace('## 一、评测背景与目标',summary+'## 一、评测背景与目标',1)
(root/'report.md').write_text(source)
body=subprocess.check_output(['pandoc','-f','gfm','-t','html5','--wrap=none'],input=source,text=True)
# Remove repeated title/metadata from body; designed cover holds metadata.
body=body[body.find('<h2'):]
for m in manifest:
    uri='data:image/svg+xml;base64,'+base64.b64encode((figdir/(m['name']+'.svg')).read_bytes()).decode()
    body=body.replace('src="figures/'+m['name']+'.png"','src="'+uri+'"')
# Wrap tables for narrow screens, preserve full data access.
body=re.sub(r'(<table>.*?</table>)',r'<div class="table-scroll">\1</div>',body,flags=re.S)
heading_list=re.findall(r'<h2 id="([^"]+)">(.*?)</h2>',body)
nav=''.join(f'<a href="#{ident}">{re.sub("<.*?>","",title)}</a>' for ident,title in heading_list)
css='''
:root{--navy:#152f49;--blue:#2463a6;--teal:#09847e;--muted:#60758b;--line:#dce6ef;--paper:#fff;--bg:#eef3f7}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--navy);font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;line-height:1.85;font-size:15px}a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.top{height:62px;background:var(--navy);color:#fff;padding:0 32px;display:flex;align-items:center;justify-content:space-between;letter-spacing:.06em}.brand{font-size:19px;font-weight:800}.top span{font-size:11px;color:#bbd1e3}.layout{max-width:1400px;margin:auto;display:grid;grid-template-columns:226px minmax(0,1fr);gap:34px;padding:36px 28px 70px}aside{position:sticky;top:24px;align-self:start;font-size:12px;max-height:92vh;overflow:auto}aside .label{font-size:10px;letter-spacing:.18em;color:var(--muted);margin:0 12px 15px}aside a{display:block;padding:8px 12px;color:var(--muted);border-left:2px solid transparent;line-height:1.55}aside a:hover{border-color:var(--teal);background:#e3edf2;color:var(--navy);text-decoration:none}.aside-note{margin:24px 12px;padding-top:20px;border-top:1px solid var(--line);font-size:11px}
main{min-width:0}.hero{padding:42px 44px 36px;background:var(--paper);border-top:5px solid var(--teal);border-radius:3px 3px 0 0}.eyebrow{color:var(--teal);font-size:11px;font-weight:700;letter-spacing:.18em}.hero h1{font-size:37px;line-height:1.3;letter-spacing:-.03em;margin:16px 0 18px}.hero h1 span{display:block;font-size:21px;color:var(--muted);font-weight:400;letter-spacing:.02em;margin-top:8px}.lead{max-width:760px;color:var(--muted);font-size:15px}.meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:20px}.meta span{font-size:11px;color:var(--muted);padding:4px 9px;border:1px solid var(--line);border-radius:3px}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.kpi{background:#fff;border:1px solid var(--line);padding:20px 18px;border-radius:4px}.kpi .value{font-size:29px;font-weight:750;line-height:1.2;color:var(--blue)}.kpi:nth-child(2) .value{color:var(--teal)}.kpi:nth-child(3) .value{color:#ad602c}.kpi .name{font-size:12px;margin-top:8px}.kpi .sub{font-size:10px;color:var(--muted);margin-top:5px}.scope{padding:14px 18px;background:#e4eef4;font-size:12px;border-left:3px solid var(--blue);margin-bottom:25px}
.article{background:white;padding:10px 44px 45px;border-radius:4px}.article h2{font-size:23px;line-height:1.5;margin:45px 0 19px;color:var(--navy);scroll-margin-top:24px}.article h3{font-size:17px;margin:30px 0 14px;color:var(--teal)}.article p{margin:15px 0}.article strong{font-weight:700}.article ul,.article ol{padding-left:24px}.article li{padding-left:3px;margin:5px 0}.article blockquote{margin:18px 0;padding:1px 18px;background:#f1f6f9;border-left:3px solid var(--teal);font-size:13px}.article img{display:block;width:100%;height:auto;margin:23px auto 6px}.article img+p{font-size:12px;color:var(--muted);line-height:1.8;padding:0 8px 15px}.table-scroll{overflow-x:auto;margin:18px 0 24px}table{width:100%;border-collapse:collapse;font-size:12px;line-height:1.7}th{background:#edf3f8;color:var(--navy);font-weight:650;text-align:left}td,th{padding:11px 12px;vertical-align:top;border-bottom:1px solid var(--line)}tbody tr:nth-child(even){background:#f8fafc}code{font-family:Consolas,monospace;font-size:.88em;background:#edf3f7;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#152f49;color:#edf4fa;padding:20px;border-radius:5px;font-size:11px;line-height:1.75}pre code{background:none;padding:0}h2+p{color:#3d5267}.footer{margin:24px 0;color:var(--muted);font-size:11px;display:flex;justify-content:space-between}.downloads{background:#fff;border:1px solid var(--line);padding:24px 28px;margin-top:22px}.downloads h2{font-size:18px;margin:0 0 12px}.download-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.download-grid a{font-size:12px;padding:9px 12px;background:#f1f6f9;border-radius:4px}button{display:inline-flex;align-items:center;justify-content:center;height:32px;line-height:1.2;white-space:nowrap;font:inherit;cursor:pointer;background:transparent;border:1px solid #8ca8be;color:#e8f0f6;border-radius:3px;padding:5px 12px;font-size:11px}
@media(max-width:900px){.layout{display:block;padding:18px 14px}aside{position:static;max-height:none;display:none}.hero{padding:30px 24px}.hero h1{font-size:29px}.article{padding:6px 22px 28px}.kpis{grid-template-columns:repeat(2,1fr)}.top{padding:0 18px}.top span{display:none}.article h2{font-size:21px}.table-scroll table{min-width:580px}.meta span{font-size:10px}}@media print{body{background:white;font-size:10pt}.top,aside,button,.downloads{display:none}.layout{display:block;padding:0;max-width:none}.hero{padding:12px 0 20px}.hero h1{font-size:26pt}.kpi{padding:12px}.kpi .value{font-size:22pt}.article{padding:0}.article h2{font-size:17pt;break-after:avoid}.article h3{break-after:avoid}.article img{break-inside:avoid;max-height:220mm;object-fit:contain}.table-scroll{overflow:visible}table{font-size:8pt;min-width:0!important}tr{break-inside:avoid}thead{display:table-header-group}a{color:inherit}pre{background:#edf3f8;color:var(--navy)}.scope{font-size:9pt}.footer{font-size:8pt}@page{size:A4;margin:15mm}
'''
downloads=''.join('<a download="'+m['name']+'.png" href="data:image/png;base64,'+base64.b64encode((figdir/(m['name']+'.png')).read_bytes()).decode()+'">'+m['title']+' · PNG ↓</a>' for m in manifest)
page='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RailMind · RAG 检索效果评测报告</title><style>'''+css+'''</style></head><body><header class="top"><div class="brand">RailMind <span> / RETRIEVAL EVALUATION</span></div><button onclick="window.print()">打印 / 保存 PDF</button></header><div class="layout"><aside><div class="label">REPORT CONTENTS</div>'''+nav+'''<div class="aside-note">数据来自已保存的逐条实测记录。<br>全部图表离线内嵌，无需联网。</div></aside><main><section class="hero"><div class="eyebrow">RAILMIND / TECHNICAL EVALUATION / 2026.09</div><h1>RAG 检索效果评测<span>从总体命中，到排序质量与失败原因</span></h1><p class="lead">围绕比赛中的检索评测分工，呈现可复现的结果、可解释的差异与明确的改进方向。</p><div class="meta"><span>评测日期 2026-09-22</span><span>版本 e5bd01d8b76a</span><span>7 个文档 ID · 26 条知识块</span><span>Top-K=3 · α=0.55</span></div></section><section class="kpis"><div class="kpi"><div class="value">31 / 31</div><div class="name">自然语言路径命中</div><div class="sub">Hit@3 · 可答题</div></div><div class="kpi"><div class="value">28 / 31</div><div class="name">关键词路径命中</div><div class="sub">Hit@3 · 可答题</div></div><div class="kpi"><div class="value">3 条</div><div class="name">关键词路径漏检</div><div class="sub">线路侧 1 条 · 车厢 2 条</div></div><div class="kpi"><div class="value">5 / 5</div><div class="name">两路径各自正确拒答</div><div class="sub">仅代表已测 5 条拒答题</div></div></section><div class="scope"><strong>评测边界：</strong>内置演示知识库上的开发回归集；结果不是独立泛化评估，也不是最终生成答案准确率。本图文版复用已核验数据，不新增实验成绩。</div><article class="article">'''+body+'''</article><section class="downloads"><h2>下载高清图表</h2><div class="download-grid">'''+downloads+'''</div></section><footer class="footer"><span>RailMind · RAG Evaluation</span><span>Measured data · Reproducible evidence</span></footer></main></div></body></html>'''
(root/'report.html').write_text(page)
(root/'chart_manifest.json').write_text(json.dumps({'source_commit':E['commit'],'source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ev.glob('*.json')},'precision_fixed_k_ceiling':ceiling,'figures':manifest},ensure_ascii=False,indent=2))
print('Generated 6 PNG, 6 SVG, portable Markdown, self-contained HTML.')
