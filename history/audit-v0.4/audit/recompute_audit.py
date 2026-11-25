"""Read-only independent aggregation of supplied ETAL v0.2/v0.3 logs.

Does not import or run training code or the original audit script. Outputs are
written next to this script, never under the supplied source directory.
"""
from pathlib import Path
import hashlib, itertools, json, platform, sys
import numpy as np
import pandas as pd
from scipy.stats import t

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT / 'source' / 'etal_v02'
OUT = Path(__file__).resolve().parent / 'audit_recomputed.json'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def interval(values):
    v = np.asarray(values, dtype=float)
    mean = float(v.mean())
    se = float(np.std(v, ddof=1) / np.sqrt(len(v)))
    k = float(t.ppf(.975, len(v)-1))
    return dict(mean=mean, lower=mean-k*se, upper=mean+k*se,
                standard_error=se, n=len(v), t_multiplier=k,
                seed_differences=v.tolist())

checks = []
for line in (SRC / 'SHA256SUMS').read_text().splitlines():
    want, rel = line.split(maxsplit=1)
    rel = rel.lstrip('*')
    p = SRC / rel
    checks.append(dict(path=rel, exists=p.is_file(),
                       matches=p.is_file() and digest(p)==want))
result = dict(scope='Read-only raw-log aggregation; no training or independent physical backend replay.',
              audit_runtime=dict(python=sys.version, platform=platform.platform(),
                                 numpy=np.__version__, pandas=pd.__version__),
              checksum=dict(files=len(checks), failures=[x for x in checks if not x['matches']]),
              contrasts=[], final_summaries=[], checks=[])
reference_contrasts = pd.read_csv(SRC / 'analysis' / 'contrasts.csv')
reference_summary = pd.read_csv(SRC / 'analysis' / 'summary.csv')
neural_test = None
for name, folder in [('base', SRC), ('high_inspect', SRC/'sensitivity'/'high_inspect'),
                     ('high_repair', SRC/'sensitivity'/'high_repair'),
                     ('high_both', SRC/'sensitivity'/'high_both'), ('neural', SRC/'neural')]:
    if name == 'neural':
        online = pd.concat([pd.read_csv(p) for p in sorted((folder/'results').glob('*/online.csv'))], ignore_index=True)
        test = pd.concat([pd.read_csv(p) for p in sorted((folder/'results').glob('*/test.csv'))], ignore_index=True)
        neural_test = test
        held = (4,3)
    else:
        online = pd.read_csv(folder/'results'/'online.csv')
        test = pd.read_csv(folder/'results'/'test.csv')
        held = (3,3)
    paired = online.groupby(['seed','arm']).reward.mean().unstack()
    for a,b in [('B3','B2'),('B4','B3')]:
        rec = dict(experiment=name, subset='online', comparison=a+'-'+b, **interval(paired[a]-paired[b]))
        ref = reference_contrasts[(reference_contrasts.experiment==name)&(reference_contrasts.subset=='online')&(reference_contrasts.comparison==a+'-'+b)].iloc[0]
        rec['matches_published_csv'] = all(abs(rec[k]-ref[k]) < 1e-10 for k in ('mean','lower','upper','standard_error','n'))
        result['contrasts'].append(rec)
    final = test[(test.phase=='after') & (test.intervention=='normal')].copy()
    final['damage_episode'] = (final.damage>0).astype(int)
    metrics=['reward','success','damage','chars','sim_seconds','tool_calls','damage_episode']
    for arm,g in final.groupby('arm'):
        rec=dict(experiment=name,arm=arm,n=len(g),**{k:float(g[k].mean()) for k in metrics})
        ref=reference_summary[(reference_summary.experiment==name)&(reference_summary.subset=='test')&(reference_summary.arm==arm)].iloc[0]
        rec['matches_published_csv']=all(abs(rec[k]-ref[k])<1e-10 for k in metrics)
        h=g[(g.fault==held[0])&(g.context==held[1])]
        rec['holdout_successes']=int(h.success.sum());rec['holdout_n']=len(h)
        result['final_summaries'].append(rec)
    sequence_match=True
    for seed,g in online.groupby('seed'):
        base=g[g.arm=='B0'].sort_values('episode')[['fault','context']].to_numpy()
        for arm,h in g.groupby('arm'):
            sequence_match &= np.array_equal(base,h.sort_values('episode')[['fault','context']].to_numpy())
    result['checks'].append(dict(experiment=name, online_rows=len(online),test_rows=len(test),
        independent_training_seeds=int(online.seed.nunique()), paired_overall_scenarios=bool(sequence_match),
        online_holdout_count=int(((online.fault==held[0])&(online.context==held[1])).sum()),
        adaptation_rows_per_seed_arm=sorted(online.groupby(['seed','arm']).size().unique().tolist()),
        candidate_rows_per_seed=sorted(online[online.arm=='B4'].groupby(['seed','candidate']).size().unique().tolist()),
        no_duplicate_online_keys=not bool(online.duplicated(['seed','arm','episode']).any())))

d = neural_test[(neural_test.phase=='after')&(neural_test.arm=='B3')]
normal = d[d.intervention=='normal'].set_index(['seed','episode'])
swap = d[d.intervention=='same_length_swap'].set_index(['seed','episode'])
action_changes = normal.macro != swap.macro
effect = normal.groupby('seed').reward.mean()-swap.groupby('seed').reward.mean()
result['neural_intervention']=dict(total_rows=len(normal),swap_count=int(swap.swapped.sum()),
    swap_coverage=float(swap.swapped.mean()), action_changes=int(action_changes.sum()),
    action_change_fraction=float(action_changes.mean()),
    action_changes_per_seed={str(k):int(v) for k,v in action_changes.groupby('seed').sum().items()},
    normal_success=float(normal.success.mean()),swapped_success=float(swap.success.mean()),
    reward_drop=interval(effect))
maps=[]
indices=[f*8+c for f in [1,4,3,0] for c in range(8)]
for p in sorted((SRC/'neural'/'results').glob('*/summary.json')):
    raw=json.loads(p.read_text())
    for m in raw['mapping']:
        maps.append(dict(seed=raw['seed'],arm=m['arm'],
                         unique_state_context_changes=sum(m['before'][i]!=m['after'][i] for i in indices)))
result['neural_mapping']={a:dict(changed=sum(m['unique_state_context_changes'] for m in maps if m['arm']==a),total=320)
                          for a in ['B2','B3','B4']}
known_before=neural_test[(neural_test.phase=='before')&(neural_test.intervention=='normal')&neural_test.fault.isin([0,1,2])]
result['neural_known_fault_readiness']={
    'definition':'Before adaptation; balanced normal/pre/ack_lost x 8 contexts x 50 channel-noise repetitions, no policy updates.',
    'mean_success_by_arm':{str(k):float(v) for k,v in known_before.groupby('arm').success.mean().items()},
    'by_seed_and_arm':[{ 'seed':int(k[0]),'arm':str(k[1]),'success':float(v)} for k,v in known_before.groupby(['seed','arm']).success.mean().items()]}
partitions={}
for arm in ['B2','B3','B4']:
    changed_contexts=changed_pairs=label_only=0;distinct_before=[];distinct_after=[]
    for path in sorted((SRC/'neural'/'results').glob('*/summary.json')):
        raw=json.loads(path.read_text());m=next(x for x in raw['mapping'] if x['arm']==arm)
        for c in range(8):
            before=[m['before'][f*8+c] for f in [1,4,3,0]]
            after=[m['after'][f*8+c] for f in [1,4,3,0]]
            label_change=sum(x!=y for x,y in zip(before,after))
            pair_change=sum((before[x]==before[y])!=(after[x]==after[y]) for x,y in itertools.combinations(range(4),2))
            changed_contexts+=pair_change>0;changed_pairs+=pair_change
            label_only+=label_change>0 and pair_change==0
            distinct_before.append(len({tuple(x) for x in before}))
            distinct_after.append(len({tuple(x) for x in after}))
    partitions[arm]=dict(contexts=80,pairs=480,changed_partition_contexts=changed_contexts,
        changed_equal_code_pairs=changed_pairs,label_changes_without_partition_change_contexts=label_only,
        mean_distinct_codes_before=float(np.mean(distinct_before)),mean_distinct_codes_after=float(np.mean(distinct_after)),
        four_distinct_codes_before=distinct_before.count(4),four_distinct_codes_after=distinct_after.count(4))
result['neural_greedy_partition_posthoc']=dict(
    caveat='Exploratory deterministic greedy-code equivalence only; not a complete stochastic semantic representation or measure of benefit. Some contexts legitimately share actions.',
    arms=partitions)
full=json.loads((SRC/'results'/'full_action.json').read_text())
result['full_action']=dict(rows=len(full['rows']),successes=sum(r['success'] for r in full['rows']),
                          total_damage=sum(r['damage'] for r in full['rows']),training_episodes=full['training_episodes'])
result['all_numerical_comparisons_match']=all(x['matches_published_csv'] for x in result['contrasts']+result['final_summaries'])
result['source_manifest_unchanged_at_end']=all(digest(SRC/x['path'])==next(l.split()[0] for l in (SRC/'SHA256SUMS').read_text().splitlines() if l.split(maxsplit=1)[1].lstrip('*')==x['path']) for x in checks)
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ['checksum','all_numerical_comparisons_match','source_manifest_unchanged_at_end','contrasts','neural_intervention','neural_mapping','full_action']},indent=2))
