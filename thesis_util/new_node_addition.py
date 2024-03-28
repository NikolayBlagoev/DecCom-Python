import random
from static_flow import *
import pandas as pd

d = {'size': [0], 'stages':[0], 'before flow': [0], 'before cost': [0], 'before cost per batch': [0], 'best actual flow': [0], 'best actual cost': [0], 'best actual cost per batch': [0], 'chosen flow': [0], 'chosen cost': [0], 'chosen cost per batch': [0]}


N = 100
d['size'] = [N]
S = 11
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
    workload.append(2000)

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
        workload.append(random.randint(10,50))
        for p in prv:
            print("update")
            cost_map[p][ttl] = random.randint(1,100)
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
indx_diff = -1
for i, c in enumerate(caps):
    # print(flows[i]/c)
    if flows[i]/c > max_next and flows[i]/c != max_bf:
        indx_diff = i
        max_next = flows[i]/c
proposed = []

for _ in range(20):
    x = random.randint(10,50)
    proposed.append((random.randint(10,50),x, x*10 + random.randint(50,100)))
print(f"Current throughput {curr_flow}")
d['before flow'] = [curr_flow]
cap_other = curr_flow / max_next
print(f"Capacity of next bottleneck {cap_other}")
best_increase = 0
best_idx = None
best_mx = float("inf")
cost_current = 2 * mx_cost_curr + max(max_costs_per_stage)
print(f"Current training cost {cost_current}")
d['before cost'] = [cost_current]
cost_per_mb = cost_current/curr_flow
d['before cost per batch'] = [cost_per_mb]
print(f"Cost per microbatch {cost_per_mb}")
for candidate, p in enumerate(proposed):
    t_new = min(cap_other, curr_flow / max_bf + p[0])
    c_new = 2*(mx_cost_curr - 2*mx_cost_curr/S + max(2*mx_cost_curr/S, 2*p[1])) + max(max(max_costs_per_stage), p[2])
    incr = (cost_current / curr_flow) - (c_new / t_new)
    print(candidate,incr, curr_flow / max_bf + p[0], p[0], cap_other, c_new, cost_current, p[1], p[2], max(max_costs_per_stage))
    if incr > best_increase:
        print("choosing candidate",candidate)
        best_increase = incr
        best_idx = p
        best_mx = p[1]*2 + p[2]
    # elif 

print(f"best new cost estimate of {best_increase}")

tmp1 = float("inf")
tmp2 = float("inf")
tmp3 = float("inf")

for candidate, p in enumerate(proposed):

    g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)


    # nd = Node(best_idx[0], ttl)
    nd = g.crt(ttl+2, p[0])
    nd_2 = g.crt(-ttl-2, p[0])
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


    find_flow(g)
    curr_flow, mx_cost_curr = eval(g)
    cost_current = 2 * mx_cost_curr + max(max(max_costs_per_stage),p[2])
    # print(f"Current training cost {cost_current}")
    # tmp1 = min(cost_current, tmp1)
    cost_per_mb = cost_current/curr_flow
    if cost_per_mb < tmp2:
        print(candidate, "smaller", cost_per_mb)
        tmp2 = cost_per_mb
        tmp1 = cost_current
        tmp3 = curr_flow
    # tmp2 = min(cost_current, tmp2)
    # print(f"Cost per microbatch {cost_per_mb}")

d['best actual cost per batch'] = [tmp2]
d['best actual cost'] = [tmp1]
d['best actual flow'] = [tmp3]

if True:
    g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)


    # nd = Node(best_idx[0], ttl)
    nd = g.crt(ttl+2, best_idx[0])
    nd_2 = g.crt(-ttl-2, best_idx[0])
    for e in g.stage_edges[indx-1]:
        to = e.to
        bck = Edge(nd,to,0,p[1])
        nrm = Edge(to,nd,2000,best_idx[1])
        bck.is_rev = True
        bck.rev = nrm
        nrm.rev = bck
        to.outgoing_edges.append(nrm)
        nd.outgoing_edges.append(bck)


    bck = Edge(nd_2,nd,0,0)
    bck.is_rev = True
    nrm = Edge(nd,nd_2,best_idx[0],0)
    bck.rev = nrm
    nrm.rev = bck
    nd.outgoing_edges.append(nrm)
    nd_2.outgoing_edges.append(bck)
    if len(g.stage_edges) != indx + 1:
        
        for e in g.stage_edges[indx+1]:
            frm = e.frm
            bck = Edge(frm,nd_2,0,best_idx[1])
            nrm = Edge(nd_2,frm,2000,best_idx[1])
            bck.is_rev = True
            bck.rev = nrm
            nrm.rev = bck
            nd_2.outgoing_edges.append(nrm)
            frm.outgoing_edges.append(bck)
    else:
        
        frm = g.t
        bck = Edge(frm,nd_2,0,best_idx[1])
        nrm = Edge(nd_2,frm,2000,best_idx[1])
        bck.is_rev = True
        bck.rev = nrm
        nrm.rev = bck
        nd_2.outgoing_edges.append(nrm)
        frm.outgoing_edges.append(bck)


    find_flow(g)
    curr_flow, mx_cost_curr = eval(g)
    cost_current = 2 * mx_cost_curr + max(max(max_costs_per_stage),best_idx[2])
    # print(f"Current training cost {cost_current}")
    
    cost_per_mb = cost_current/curr_flow
    d['chosen cost per batch'] = [cost_per_mb]
    d['chosen flow'] = curr_flow
    d['chosen cost'] = cost_current
    print(f"Cost per microbatch {cost_per_mb}")
print(d)
df = pd.DataFrame(data=d)
df.to_csv("results.csv", mode='a', header=False, index=1)
