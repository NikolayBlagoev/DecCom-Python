import random
from static_flow import *
import pandas as pd
import itertools
from tqdm import tqdm

d = {'size': [0], 'stages':[0], 'before flow': [0], 'before cost': [0], 'before cost per batch': [0], 'best actual flow': [0], 'best actual cost': [0], 'best actual cost per batch': [0], 'chosen flow': [0], 'chosen cost': [0], 'chosen cost per batch': [0]}
def add_node(g: Graph,ttl,p,i,indx):
        nd = g.crt(ttl+2+i, p[0])
        nd_2 = g.crt(-ttl-i, p[0])
        for e in g.stage_edges[indx-1]:
            to = e.to
            bck = Edge(nd,to,0,p[1])
            nrm = Edge(to,nd,2000,p[1])
            bck.is_rev = True
            bck.rev = nrm
            nrm.rev = bck
            to.outgoing_edges.append(nrm)
            nd.outgoing_edges.append(bck)


        bck = Edge(nd_2,nd,0,0)
        bck.is_rev = True
        nrm = Edge(nd,nd_2,p[0],0)
        bck.rev = nrm
        nrm.rev = bck
        nd.outgoing_edges.append(nrm)
        nd_2.outgoing_edges.append(bck)
        if len(g.stage_edges) != indx + 1:
            
            for e in g.stage_edges[indx+1]:
                frm = e.frm
                bck = Edge(frm,nd_2,0,p[1])
                nrm = Edge(nd_2,frm,2000,p[1])
                bck.is_rev = True
                bck.rev = nrm
                nrm.rev = bck
                nd_2.outgoing_edges.append(nrm)
                frm.outgoing_edges.append(bck)
        else:
            
            frm = g.t
            bck = Edge(frm,nd_2,0,p[1])
            nrm = Edge(nd_2,frm,2000,p[1])
            bck.is_rev = True
            bck.rev = nrm
            nrm.rev = bck
            nd_2.outgoing_edges.append(nrm)
            frm.outgoing_edges.append(bck)

N = 97
d['size'] = [N]
S = 8
to_add = 1
to_add = min(to_add, S)
d['stages'] = [S]
cost_map = []
for _ in range(N):
    cost_map.append([float("inf") for _ in range(N)])
dataholders: list[int] = []
dataholder_count = 1
workload = []
for i in range(dataholder_count):
    dataholders.append(i)
    ttl = i+1
    workload.append(6000)

per_stage = (N - dataholder_count)//S

assignment = []
assignment.append(dataholders)
prv = dataholders
max_costs_per_stage = [1]
for i in range(S):
    tmp = []
    mx_send = 0
    for _ in range(per_stage):
        tmp.append(ttl)
        workload.append(random.randint(1,20))
        for p in prv:
            print("update")
            cost_map[p][ttl] = random.randint(20,100)
            cost_map[ttl][p] = cost_map[p][ttl]
            mx_send = max(cost_map[p][ttl], mx_send)
        ttl+=1
    max_costs_per_stage.append(mx_send*10 + random.randint(50,100))
    assignment.append(tmp)
    prv = tmp

print(cost_map)
g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)
find_flow(g)
curr_flow, mx_cost_curr = eval(g)
caps = []
flows = []
for s in g.stage_edges:
    # print("---")
    cap_t = 0
    flow_t = 0
    for e in s:
        # print(e.flow, e.cap)
        cap_t += e.cap
        flow_t += e.flow
    caps.append(cap_t)
    flows.append(flow_t)
# print("---")
max_bf = 0
indx = -1
for i, c in enumerate(caps):
    # print(flows[i]/c)
    if flows[i]/c > max_bf:
        indx = i
        max_bf = flows[i]/c
max_next = 0
capacities = []
indx_diff = -1
for i, c in enumerate(caps):
    # print(flows[i]/c)
    capacities.append((c, i))
    if flows[i]/c > max_next and i != indx:
        indx_diff = i
        max_next = flows[i]/c
proposed = []

for _ in range(20):
    x = random.randint(1,20)
    proposed.append((random.randint(20,100),x, x*10 + random.randint(50,100)))
print(f"Current throughput {curr_flow}")
d['before flow'] = [curr_flow]
cap_other = curr_flow / max_next
print(f"Capacity of next bottleneck {cap_other}")

cost_current = 2 * mx_cost_curr + max(max_costs_per_stage)
print(f"Current training cost {cost_current}")
d['before cost'] = [cost_current]
cost_per_mb = cost_current/curr_flow
d['before cost per batch'] = [cost_per_mb]
print(f"Cost per microbatch {cost_per_mb}")
chosen_best = []
for i in range(to_add):
    choice = None
    indx = 0
    tmp =  list(enumerate(caps))
    tmp = sorted(tmp, key=lambda x: x[0], reverse=True)

    indx = tmp[i][0]
    if indx == 0:
        break
    curr_flow_loc = tmp[i-1][0] if i > 0 else curr_flow
    cap_other = tmp[i][1]
    for phi in range(i,len(tmp)):
        if tmp[phi][1] != tmp[i][1]:
            cap_other = tmp[phi][1]
            break
    best_increase = 0
    
    best_mx = float("inf")
    for candidate, p in enumerate(proposed):
        if p in chosen_best:
            continue
        t_new = min(cap_other, curr_flow_loc / max_bf + p[0])
        c_new = 2*(mx_cost_curr - 2*mx_cost_curr/S + max(2*mx_cost_curr/S, 2*p[1])) + max(max(max_costs_per_stage), p[2])
        incr = (cost_current / curr_flow_loc) - (c_new / t_new)
        
        if incr > best_increase:
            print("choosing candidate",candidate)
            best_increase = incr
            choice = p
            best_mx = p[1]*2 + p[2]
        
    if choice == None:
        break
    chosen_best.append(choice)


print(f"best new cost estimate of {best_increase}")

tmp1 = float("inf")
tmp2 = float("inf")
tmp3 = float("inf")

choices_possible = list(itertools.combinations(proposed, to_add))
for p_list in tqdm(choices_possible):
    g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)
    for i, p in enumerate(p_list):
        indx = 0
        tmp =  list(enumerate(caps))
        tmp = sorted(tmp, key=lambda x: x[0], reverse=True)
        
        
        indx = tmp[i][0]
        if indx == 0:
            break
        add_node(g,ttl,p, i,indx)
        


    find_flow(g)
    curr_flow, mx_cost_curr = eval(g, False)
    cost_current = 2 * mx_cost_curr + max(max(max_costs_per_stage),p[2])
        # print(f"Current training cost {cost_current}")
        # tmp1 = min(cost_current, tmp1)
    cost_per_mb = cost_current/curr_flow
    if cost_per_mb < tmp2:
        print("smaller", cost_per_mb)
        
        tmp2 = cost_per_mb
        tmp1 = cost_current
        tmp3 = curr_flow
        
    

d['best actual cost per batch'] = [tmp2]
d['best actual cost'] = [tmp1]
d['best actual flow'] = [tmp3]
g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)
for i, p in enumerate(chosen_best):
    tmp =  list(enumerate(caps))
    tmp = sorted(tmp, key=lambda x: x[0], reverse=True)
        
    indx = tmp[i][0]
    print("adding to stage ",indx)
    add_node(g,ttl,p, i,indx)

find_flow(g)
curr_flow, mx_cost_curr = eval(g)
cost_current = 2 * mx_cost_curr + max(max(max_costs_per_stage),p[2])
cost_per_mb = cost_current/curr_flow
d['chosen cost per batch'] = [cost_per_mb]
d['chosen flow'] = curr_flow
d['chosen cost'] = cost_current
print(d)
df = pd.DataFrame(data=d)
df.to_csv("results3.csv", mode='a', header=False, index=1)
