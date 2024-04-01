import random
from typing import Dict, Tuple
import heapq

class Node():
    def __init__(self, cap: int, id: int) -> None:
        self.outgoing_edges: list[Edge] = []
        self.cap: int = cap
        self.id: int = id
        self.cost_to_source: float = 100000
        self.p_smallest: Node = None
        self.flow: int = 0
        self.visited = False
    

class Edge():
    def __init__(self,frm: Node, to: Node, cap: int, cost: int) -> None:
        self.to: Node = to
        self.frm: Node = frm
        self.cap: int = cap
        self.cost: float = cost
        self.flow: int = 0
        self.rev: Edge = None
        self.is_rev: bool = False
        self.resid = self.cap - self.flow
    




class Graph():
    def __init__(self) -> None:
        self.s = Node(2**30, 1)
        self.t = Node(2**30, -1)
        self.node_d: Dict[int, Node] = dict()
        self.stage_edges: list[list[Edge]] = []
    def crt(self, id: int, cap: int) -> Node:
        nw = Node(cap, id)
        self.node_d[id] = nw
        return nw
    
    
def make_graph(cost_matrix: list[list[int]], assignm: list[list[int]], cap: list[int], link_cap: list[list[int]] = None) -> Graph:
    g = Graph()
    
    prev_row: list[Node] = []
    stage = 0
    for l in assignm:
        curr_row: list[Node] = []
        for n in l:
            # print(n)
            nw = g.node_d.get(n+2)
            bck = g.node_d.get(-(n+2))
            if nw == None:
                nw = g.crt(n+2, cap[n])
                bck = g.crt(-(n+2), cap[n])
            curr_row.append(bck)
            for p in prev_row:
                nrm = Edge(p,nw,link_cap[-p.id-2][n] if link_cap != None else 20000,cost_matrix[-p.id-2][n])
                rev = Edge(nw,p,0,cost_matrix[-p.id-2][n])
                rev.is_rev = True
                rev.rev = nrm
                nrm.rev = rev
                p.outgoing_edges.append(nrm)
                nw.outgoing_edges.append(rev)
            if len(prev_row)==0:
                nrm = Edge(g.s,nw,200000,0)
                rev = Edge(nw,g.s,0,0)
                rev.is_rev = True
                rev.rev = nrm
                nrm.rev = rev
                g.s.outgoing_edges.append(nrm)
                nw.outgoing_edges.append(rev)
            nrm = Edge(nw,bck,cap[n],0)
            if len(g.stage_edges) <= stage:
                g.stage_edges.append([])
            g.stage_edges[stage].append(nrm)
            rev = Edge(bck,nw,0,0)
            rev.is_rev = True
            rev.rev = nrm
            nrm.rev = rev
            nw.outgoing_edges.append(nrm)
            bck.outgoing_edges.append(rev)
        stage += 1
        prev_row = curr_row
    for p in prev_row:
        # print("connecting to end with ",cap[-p.id-2],)
        nrm = Edge(p,g.t,cap[-p.id-2],0)
        rev = Edge(g.t,p,0,0)
        rev.is_rev = True
        rev.rev = nrm
        nrm.rev = rev
        p.outgoing_edges.append(nrm)
        g.t.outgoing_edges.append(rev)
        
    return g

def find_flow(g: Graph):
    while True:
        for i,n in g.node_d.items():
            n.cost_to_source = float("inf")
            n.p_smallest = None
            n.visited = False
        g.t.p_smallest = None
        g.t.cost_to_source = float("inf")
        g.t.visited = False
        g.s.visited = False
        q:list[Tuple[int, int, Node, Node]] = []
        heapq.heapify(q)
        heapq.heappush(q,(0, 0, g.s, None))
        idx = 1
        # Find shortest pat:
        visited_target = False
        
        while not visited_target and len(q)>0:
            c,id,el,p = heapq.heappop(q)
            if el.visited:
                continue
            el.visited = True
            # if el.flow == el.cap:
            #     continue
            
            el.cost_to_source = c
            el.p_smallest = p
            if el.id == g.t.id:
                break
            
            for p in el.outgoing_edges:
                
                if p.resid > 0:
                    
                    heapq.heappush(q,(c+p.cost, idx, p.to, el))
                    idx+=1
        # print("found path")
        if g.t.p_smallest == None:
            break
        # print("iter")
        # push flow on path:
        pth: list[Node] = []
        cur = g.t
        
        while cur != None:
            pth.append(cur)
            cur = cur.p_smallest
        # print(len(pth))
        pth.reverse()
        edge_path: list[Edge] = []
        vl: int = 2**30 # very very large
        for i in range(len(pth)-1):
            for e in pth[i].outgoing_edges:
                if e.to == pth[i+1]:
                    edge_path.append(e)
                    vl = min(vl, e.resid)
                    break
        # for n in pth:
        #     n.flow += vl
        for e in edge_path:
            e.flow += vl
            e.resid = e.cap - e.flow
            e.rev.flow -= vl
            e.rev.resid = e.rev.cap - e.rev.flow

def eval(g: Graph, verbose = True):
    flw = 0
    for edg in g.t.outgoing_edges:
        flw-=edg.flow
    if verbose:
        print(f"WE CAN ACHIEVE A FLOW OF ${flw}")
    cost: float = 0
    max_cost: float = 0
    for i, n in g.node_d.items():
        
        for edg in n.outgoing_edges:
            if not edg.is_rev and edg.flow > 0:
                # if abs(edg.frm.id) != abs(edg.to.id):
                    # print(f"NODE ${abs(edg.frm.id) - 2} communicates with ${abs(edg.to.id) - 2} with flow of ${edg.flow}")
                cost+=edg.cost*edg.flow
                max_cost = max(edg.cost*edg.flow, max_cost)
    if verbose:
        print(f"WITH TOTAL PIPELINE COST ${cost} ")
    #print(f"WITH MAXIMUM PIPELINE COST ${max_cost} ")
    max_cost: float = 0
    prevl = [g.s]
    while True:
        if prevl[0] == g.t:
            break
        curl = []
        cur_max = float("-inf")
        for cur in prevl:
            
            for edg in cur.outgoing_edges:
                if not edg.is_rev:
                    if edg.flow > 0:
                        cur_max = max(cur_max, edg.cost)
                    if edg.to not in curl:
                        curl.append(edg.to)
        prevl = curl
        max_cost += cur_max
    #print(f"AND MAX COST {2*max_cost}")
    return flw, max_cost

import json    
if __name__ == "__main__":  
    config = {}
    N = 33
    config['N'] = N
    S = 8
    config['S'] = S
    cost_map = []
    dataholder_count = 1
    for _ in range(N+dataholder_count):
        cost_map.append([70_000 for _ in range(N+dataholder_count)])
    dataholders: list[int] = []
    
    workload = []
    for i in range(dataholder_count):
        dataholders.append(i)
        ttl = i+1
        workload.append(20)

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
            workload.append(random.randint(2,5))
            for p in prv:
                # print("update")
                cost_map[p][ttl] = random.randint(1,10)
                cost_map[ttl][p] = cost_map[p][ttl]

                for bv in range(dataholder_count):
                    cost_map[bv][ttl] = random.randint(1,10)
                    cost_map[ttl][bv] = cost_map[bv][ttl]
                    cost_map[N+bv][ttl] = cost_map[bv][ttl]
                    cost_map[ttl][N+bv] = cost_map[bv][ttl]

                mx_send = max(cost_map[p][ttl], mx_send)
            ttl+=1
        max_costs_per_stage.append(mx_send*10 + random.randint(250,1000))
        assignment.append(tmp)
        prv = tmp
    sinks = []
    for i in range(dataholder_count):
        sinks.append(ttl)
        workload.append(20)
        ttl+=1
    
    assignment.append(sinks)
    
    g = make_graph(cost_matrix=cost_map, assignm=assignment, cap = workload)
    find_flow(g)

    curr_flow, mx_cost_curr = eval(g)
    config['workload'] = workload
    config['assignment'] = assignment
    config['costmap'] = cost_map
    with open("config.json", "w") as js:
        js.write(json.dumps(config, indent=2))
    
    # print(cost_map)
    
    

