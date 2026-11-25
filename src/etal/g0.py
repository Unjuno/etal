"""Exact one-decision information-value diagnostic.

States (x,y) are equally likely in N and C; actions are bits. The same reward
(success=1, failure=0) is used throughout. In N the correct action is x; in C
it is y. F changes the probability of x, but not the correct action.
Sender observes state, receiver sees a fixed-width code or pays to inspect.
This is an abstract model of a consequence shift, not a stateful tool run.
Enumerates all deterministic encoders and computes optimal decoder/inspection.
All arithmetic is rational. Costs are dimensionless utility, not measured time.
"""
from fractions import Fraction as Q
from itertools import product
import argparse
import csv
from pathlib import Path

STATES = tuple(product(range(2), repeat=2))
UNIFORM = (Q(1,4),)*4
FREQUENCY = (Q(3,8), Q(3,8), Q(1,8), Q(1,8))
TASKS = {"N": (UNIFORM, tuple(x for x,y in STATES)),
         "C": (UNIFORM, tuple(y for x,y in STATES)),
         "F": (FREQUENCY, tuple(x for x,y in STATES))}


def encoders(bits):
    if bits not in (0,1,2):
        raise ValueError("bits must be 0, 1, or 2")
    return product(range(2**bits), repeat=len(STATES))


def utility(code, bits, branch, bit_cost, inspect_cost):
    """Bayes-optimal receiver chooses action 0/1 or paid perfect inspection.

    The same inspection option is available for all codecs, including silence.
    Each code uses exactly bits payload bits per decision. No framing modeled.
    """
    p, target = TASKS[branch]
    total = Q(0)
    for m in range(2**bits):
        a = sum((w for i,w in enumerate(p) if code[i]==m and target[i]==0), Q(0))
        b = sum((w for i,w in enumerate(p) if code[i]==m and target[i]==1), Q(0))
        total += max(a,b,(a+b)*(1-inspect_cost))
    return total-bits*bit_cost


def best(bits, branch, bit_cost, inspect_cost):
    scored=[(utility(c,bits,branch,bit_cost,inspect_cost),c) for c in encoders(bits)]
    optimum=max(v for v,_ in scored)
    return optimum, [c for v,c in scored if v==optimum]


def row(bits, branch, bit_cost, inspect_cost, switch_cost, horizon):
    if min(bit_cost, inspect_cost, switch_cost)<0 or horizon<1:
        raise ValueError("costs must be nonnegative and horizon positive")
    # Fixed source-optimal code: report full range across ties, not favorable tie.
    pre, pre_codes=best(bits,"N",bit_cost,inspect_cost)
    post, _=best(bits,branch,bit_cost,inspect_cost)
    fixed=[utility(c,bits,branch,bit_cost,inspect_cost) for c in pre_codes]
    adaptive=[max(v,post-switch_cost/horizon) for v in fixed]
    gains=[a-v for a,v in zip(adaptive,fixed)]
    # Strong non-adaptive baseline: optimum static code with hindsight of both
    # phases, equal phase lengths; decoder may adapt. A separate full-information
    # static comparator has two bits and a source-independent identity code.
    static_joint=max((utility(c,bits,"N",bit_cost,inspect_cost)+
                      utility(c,bits,branch,bit_cost,inspect_cost))/2 for c in encoders(bits))
    identity=tuple(range(4))
    return dict(branch=branch,bits=bits,bit_cost=bit_cost,inspect_cost=inspect_cost,
                switch_cost=switch_cost,horizon=horizon,source_optimum=pre,
                source_optimal_ties=len(pre_codes),fixed_post_min=min(fixed),
                fixed_post_max=max(fixed),adaptive_post_min=min(adaptive),
                adaptive_post_max=max(adaptive),gain_min=min(gains),gain_max=max(gains),
                static_joint_mean=static_joint,
                no_message_post=utility((0,)*4,0,branch,bit_cost,inspect_cost),
                sufficient_fixed_post=utility(identity,2,branch,bit_cost,inspect_cost))


def grid():
    for b,c,i,s,h,branch in product((0,1,2),(Q(0),Q(1,20),Q(1,5),Q(3,5)),
            (Q(0),Q(1,10),Q(2,5),Q(1)),(Q(0),Q(1),Q(10)),(10,100),("N","C","F")):
        yield row(b,branch,c,i,s,h)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('results/g0_grid.csv'))
    args=parser.parse_args(); rows=list(grid()); args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f"Wrote {len(rows)} exact diagnostic cells to {args.out}")

if __name__=='__main__': main()
