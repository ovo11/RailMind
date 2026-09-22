"""Read-only RailMind retrieval audit. python audit_rag.py --repo /path/RailMind --out ./results"""
import argparse
import collections
import dataclasses
import datetime
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--out', required=True)
a = p.parse_args()
repo = Path(a.repo).resolve()
out = Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo))
import numpy
import scipy
import sklearn
from railmind.core.rag import RagClient, _expand_query
from railmind.core.rag_eval import RagEvaluator, GOLDEN_DATASET

def write(name, obj):
    (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def metrics(rows, path, k):
    ans = [r for r in rows if not r.case.should_refuse]
    neg = [r for r in rows if r.case.should_refuse]
    sums = collections.defaultdict(float)
    fails = []
    ranks = collections.Counter()
    for r in ans:
        ids = getattr(r, path + '_ids')[:k]
        hits = [int(x in r.case.relevant) for x in ids]
        rank = next((i+1 for i, hit in enumerate(hits) if hit), None)
        ranks[str(rank)] += 1
        sums['hit'] += bool(rank)
        sums['mrr'] += 1/rank if rank else 0
        sums['precision_fixed_k'] += sum(hits)/k
        sums['precision_returned'] += sum(hits)/len(ids) if ids else 0
        sums['recall'] += len(set(ids) & r.case.relevant)/len(r.case.relevant)
        dcg = sum(hit/math.log2(i+2) for i,hit in enumerate(hits))
        idcg = sum(1/math.log2(i+2) for i in range(min(len(r.case.relevant),k)))
        sums['ndcg'] += dcg/idcg
        sums['false_refusal_rate'] += getattr(r,path+'_refused')
        if not rank:
            fails.append({'case_id':r.case.case_id,'query':r.case.query,'keywords':r.case.keywords,'expected':sorted(r.case.relevant),'returned':ids})
    ret = {key:round(value/len(ans),6) for key,value in sums.items()}
    ret.update(answerable=len(ans), refusal=len(neg), hit_count=int(sums['hit']), rank_counts=dict(ranks), failures=fails)
    ret['correct_refusal_rate'] = sum(getattr(r,path+'_refused') for r in neg)/len(neg) if neg else None
    ret['short_returns'] = sum(len(getattr(r,path+'_ids'))<k for r in ans)
    return ret

client=RagClient(top_k=3,alpha=.55)
ev=RagEvaluator(client,top_k=3)
original=ev.run()
write('audit_upstream_summary.json',original)
rows=[]
for r in ev.results:
    row=dataclasses.asdict(r)
    row['case']['relevant']=sorted(r.case.relevant)
    rows.append(row)
write('all_36_cases.json',rows)
summary={path:metrics(ev.results,path,3) for path in ['search','retrieve']}
summary['by_domain']={domain:{path:metrics([r for r in ev.results if r.case.domain==domain],path,3) for path in ['search','retrieve']} for domain in sorted({r.case.domain for r in ev.results if not r.case.should_refuse})}
summary['by_difficulty']={diff:{path:metrics([r for r in ev.results if not r.case.should_refuse and r.case.difficulty==diff],path,3) for path in ['search','retrieve']} for diff in ['easy','medium','hard']}
chunks=client.list_chunks()
refs={(c.document_id,c.chapter) for c in chunks}
gold=set().union(*(c.relevant for c in GOLDEN_DATASET))
summary['coverage']={'physical_chunks':len(chunks),'unique_doc_chapter':len(refs),'gold_doc_chapter':len(gold),'missing_gold':sorted(gold-refs),'uncovered_doc_chapter':sorted(refs-gold),'domain_chunk_counts':dict(collections.Counter(c.asset_type for c in chunks))}
summary['duplicate_keyword_queries']=[{'asset_type':asset,'keywords':list(kw),'case_ids':[c.case_id for c in cases],'distinct_gold_sets':len({tuple(sorted(c.relevant)) for c in cases})} for (asset,kw),cases in ((key,[c for c in GOLDEN_DATASET if (c.asset_type,tuple(c.keywords or []))==key]) for key in sorted({(c.asset_type,tuple(c.keywords or [])) for c in GOLDEN_DATASET})) if len(cases)>1]
write('audited_metrics.json',summary)

failure_scores=[]
failed_ids={x['case_id'] for x in summary['retrieve']['failures']}
for case in GOLDEN_DATASET:
    if case.case_id not in failed_ids:
        continue
    indices=client.kb.filter(asset_type=case.asset_type)
    sem=client.kb._semantic_scores(_expand_query(' '.join(case.keywords)),indices)
    kw=client.kb._keyword_scores(case.keywords,indices)
    for j,i in enumerate(indices):
        chunk=client.kb.chunks[i]
        if (chunk.document_id,chunk.chapter) in case.relevant:
            failure_scores.append({'case_id':case.case_id,'chapter':chunk.chapter,'tfidf_cosine':float(sem[j]),'keyword_score':float(kw[j]),'gate':.08})
write('failure_scores.json',failure_scores)

# Sensitivity only: same fitted corpus, query expansion, and refusal gates;
# alpha=0 is NOT a threshold-free BM25 baseline.
sensitivity=[]
base_ids={path:[getattr(r,path+'_ids') for r in ev.results] for path in ['search','retrieve']}
for k,alpha in [(1,.55),(5,.55),(3,0.0),(3,1.0)]:
    e=RagEvaluator(RagClient(top_k=k,alpha=alpha),top_k=k)
    e.run()
    item={'top_k':k,'alpha':alpha}
    for path in ['search','retrieve']:
        item[path]=metrics(e.results,path,k)
        if k==3:
            item[path]['identical_rankings_to_default']=sum(getattr(r,path+'_ids')==base_ids[path][i] for i,r in enumerate(e.results))
    sensitivity.append(item)
write('sensitivity.json',sensitivity)

files=['railmind/core/rag.py','railmind/core/rag_eval.py','scripts/eval_rag.py','railmind/core/chat.py','railmind/core/chief.py']
checksums={f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files}
cpu='unavailable'
cpuinfo=Path('/proc/cpuinfo')
if cpuinfo.exists():
    cpu=next((line.split(':',1)[1].strip() for line in cpuinfo.read_text().splitlines() if line.startswith('model name')),cpu)
env={'measured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'python':sys.version,'platform':platform.platform(),'cpu':cpu,'logical_cpus_visible':os.cpu_count(),'numpy':numpy.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'sha256':checksums,'latency_protocol':'One sequential pass per path over 36 cases; index warmed; no network/LLM; wall-clock via perf_counter; shared execution environment.'}
write('environment.json',env)
print(json.dumps({'metrics':summary,'sensitivity':sensitivity,'environment':env},ensure_ascii=False,indent=2))
