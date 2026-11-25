"""Verify design examples; these are planning calculations, not ETAL outcomes."""
from pathlib import Path
import json,math
from scipy.stats import nct,t

root=Path(__file__).resolve().parents[1]
records=[]
for sd in (.03,.06,.09):
    minimum=next(n for n in range(3,10001)
                 if nct.sf(t.ppf(.975,n-1),n-1,(.05-.02)*math.sqrt(n)/sd)>=.90)
    selected=max(30,math.ceil(minimum/10)*10)
    records.append({'paired_sd':sd,'minimum_n':minimum,'rounded_n':selected,
                    'within_cap':selected<=100,'planning_effect':.05,'margin':.02,'power':.90})
result={'kind':'planning_examples_not_experiment_results','power_examples':records,
        'fixed_model_zero_hazard_upper':1-(.05/30)**(1/1000),
        'one_environment_minimum_adaptation_jobs':9*3*4*5000*30,
        'one_environment_maximum_adaptation_jobs':9*3*4*5000*100,
        'illustrative_utility':1-.1*.5-.02*.25-1*0-.05*.2}
(root/'analysis'/'planning_numbers.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
