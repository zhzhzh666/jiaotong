"""Budget constrained, truly re-evaluated marginal-gain greedy and enumeration."""
from itertools import combinations
import numpy as np
import pandas as pd


def greedy(candidates,costs,budget,k,evaluate):
    selected=[];trace=[];base=evaluate(tuple())
    while len(selected)<k:
        feasible=[e for e in candidates if e not in selected and sum(costs[x] for x in selected)+costs[e]<=budget+1e-12]
        if not feasible:break
        trials=[(float((evaluate(tuple(selected+[e]))-base)/costs[e]),str(e),e) for e in feasible]
        gain,_,choice=max(trials,key=lambda t:(t[0],t[1]))
        if gain<=1e-12:break # no requirement to spend on harmful or zero-value actions
        selected.append(choice);new=evaluate(tuple(selected));trace.append({'iteration':len(selected),'road_id':choice,'marginal_gain_per_cost':gain,'objective':new});base=new
    return selected,pd.DataFrame(trace)


def exhaustive(candidates,costs,budget,k,evaluate):
    best=tuple();value=evaluate(best);count=0
    for size in range(min(k,len(candidates))+1):
        for choice in combinations(candidates,size):
            if sum(costs[e] for e in choice)<=budget+1e-12:
                score=evaluate(choice);count+=1
                if score>value:best=choice;value=score
    return list(best),float(value),count


def fixed_selection(order,costs,budget,k):
    selected=[]
    for e in order:
        if len(selected)<k and sum(costs[x] for x in selected)+costs[e]<=budget+1e-12:selected.append(e)
    return selected


def confidence_interval(values):
    from scipy.stats import t
    a=np.asarray(values,float);n=len(a);sd=float(a.std(ddof=1)) if n>1 else 0.;margin=float(t.ppf(.975,n-1)*sd/np.sqrt(n)) if n>1 else 0.
    return {'n':n,'mean':float(a.mean()),'std':sd,'ci95_low':float(a.mean()-margin),'ci95_high':float(a.mean()+margin)}
