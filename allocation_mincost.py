#!/usr/bin/env python3
import csv
import math
from collections import defaultdict, deque

# Min-cost max-flow implementation (successive shortest path with potentials)
class MinCostMaxFlow:
    def __init__(self, n):
        self.n = n
        self.adj = [[] for _ in range(n)]

    def add_edge(self, u, v, cap, cost):
        self.adj[u].append([v, cap, cost, len(self.adj[v])])
        self.adj[v].append([u, 0, -cost, len(self.adj[u]) - 1])

    def min_cost_flow(self, s, t, maxf=10**9):
        n = self.n
        prevv = [0]*n
        preve = [0]*n
        INF = 10**18
        res = 0
        h = [0]*n  # potentials
        dist = [0]*n
        flow = 0
        while flow < maxf:
            # Dijkstra
            import heapq
            for i in range(n): dist[i] = INF
            dist[s] = 0
            pq = [(0, s)]
            while pq:
                d, v = heapq.heappop(pq)
                if dist[v] < d: continue
                for i, e in enumerate(self.adj[v]):
                    to, cap, cost, rev = e
                    if cap > 0 and dist[to] > dist[v] + cost + h[v] - h[to]:
                        dist[to] = dist[v] + cost + h[v] - h[to]
                        prevv[to] = v
                        preve[to] = i
                        heapq.heappush(pq, (dist[to], to))
            if dist[t] == INF:
                break
            for v in range(n):
                if dist[v] < INF:
                    h[v] += dist[v]
            d = maxf - flow
            v = t
            while v != s:
                d = min(d, self.adj[prevv[v]][preve[v]][1])
                v = prevv[v]
            flow += d
            res += d * h[t]
            v = t
            while v != s:
                e = self.adj[prevv[v]][preve[v]]
                e[1] -= d
                self.adj[v][e[3]][1] += d
                v = prevv[v]
        return flow, res


def load_mentee_preferences(file_path):
    mentees = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prefs = [row.get('Pref1','').strip(), row.get('Pref2','').strip(), row.get('Pref3','').strip(), row.get('Pref4','').strip(), row.get('Pref5','').strip()]
            prefs = [p for p in prefs if p]
            mentees.append({'roll': row.get('Roll Number','').strip(), 'name': row.get('Full Name','').strip(), 'prefs': prefs})
    return mentees


def load_mentors(file_path):
    mentors = {}
    code_to_mentors = defaultdict(list)
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Full Name','').strip()
            codes = [c.strip() for c in row.get('Project Codes','').split(';') if c.strip()]
            mentors[name] = {'codes': codes}
            for c in codes:
                code_to_mentors[c].append(name)
    return mentors, code_to_mentors


def build_and_solve(mentees, mentors, code_to_mentors, prefer_costs=(0,1,2,3,4), penalty_new_code=0.3):
    # nodes:
    # source (0)
    # mentee nodes [1..M]
    # code nodes [M+1 .. M+C]
    # mentor nodes [M+C+1 .. M+C+T]
    # sink last
    M = len(mentees)
    codes = sorted(code_to_mentors.keys())
    C = len(codes)
    mentor_list = list(mentors.keys())
    T = len(mentor_list)

    code_index = {code: i for i, code in enumerate(codes)}
    mentor_index = {m: i for i, m in enumerate(mentor_list)}

    S = 0
    mentee_start = 1
    code_start = mentee_start + M
    mentor_start = code_start + C
    T_node = mentor_start + T
    total_nodes = T_node + 1

    mcmf = MinCostMaxFlow(total_nodes)

    # source -> mentee
    for i in range(M):
        mcmf.add_edge(S, mentee_start + i, 1, 0)

    # mentee -> code edges (only their preferences)
    for i, mentee in enumerate(mentees):
        for rank, code in enumerate(mentee['prefs']):
            if code in code_index:
                cost = prefer_costs[rank]
                # lower cost for earlier preferences
                mcmf.add_edge(mentee_start + i, code_start + code_index[code], 1, cost)
        # Add fallback edges to any code with a large cost so every mentee can be assigned
        # This ensures the solver prioritizes preferences but will still assign everyone
        fallback_cost = max(prefer_costs) + 1000
        for code in codes:
            if code not in mentee['prefs']:
                mcmf.add_edge(mentee_start + i, code_start + code_index[code], 1, fallback_cost)

    # code -> mentor edges
    for code, idx in code_index.items():
        for mentor in code_to_mentors.get(code, []):
            mi = mentor_index[mentor]
            # cost add small penalty for each mentee using this mentor-code (soft discourage many codes)
            # This is linear; it won't strictly limit distinct codes but will bias towards fewer codes per mentor
            mcmf.add_edge(code_start + idx, mentor_start + mi, 8, int(penalty_new_code * 1000))

    # mentor -> sink edges (capacity 8)
    for mi in range(T):
        mcmf.add_edge(mentor_start + mi, T_node, 8, 0)

    # Run min-cost max-flow aiming to assign as many mentees as possible
    max_flow = M
    flow, cost = mcmf.min_cost_flow(S, T_node, max_flow)

    # Extract assignments by inspecting edges mentee->code where flow used
    assignments = [None] * M
    # loop over mentee->code edges
    for i in range(M):
        for e in mcmf.adj[mentee_start + i]:
            to, cap, cst, rev = e
            # if original capacity was 1 and now 0 then used; but we don't have original; check reverse flow
            # reverse edge exists at mcmf.adj[to][rev]
            rev_edge = mcmf.adj[to][rev]
            if rev_edge[1] > 0 and code_start <= to < mentor_start:
                code_idx = to - code_start
                code_name = codes[code_idx]
                # now find which mentor node received flow from this code
                # search edges from code node to mentors
                for e2 in mcmf.adj[to]:
                    to2, cap2, cst2, rev2 = e2
                    if mentor_start <= to2 < T_node:
                        # reverse edge flow indicates used
                        rev_e2 = mcmf.adj[to2][rev2]
                        if rev_e2[1] > 0:
                            mentor_name = mentor_list[to2 - mentor_start]
                            assignments[i] = (code_name, mentor_name)
                            break
                if assignments[i]:
                    break

    return assignments, flow, cost, mentees, mentor_list


def write_results(mentees, assignments, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Roll Number', 'Full Name', 'Assigned Mentor', 'Assigned Code', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mentee, assign in zip(mentees, assignments):
            assigned_code = ''
            assigned_mentor = ''
            if assign:
                assigned_code, assigned_mentor = assign
            writer.writerow({
                'Roll Number': mentee['roll'],
                'Full Name': mentee['name'],
                'Assigned Mentor': assigned_mentor,
                'Assigned Code': assigned_code,
                'Pref1': mentee['prefs'][0] if len(mentee['prefs'])>0 else '',
                'Pref2': mentee['prefs'][1] if len(mentee['prefs'])>1 else '',
                'Pref3': mentee['prefs'][2] if len(mentee['prefs'])>2 else '',
                'Pref4': mentee['prefs'][3] if len(mentee['prefs'])>3 else '',
                'Pref5': mentee['prefs'][4] if len(mentee['prefs'])>4 else ''
            })


def main():
    mentees = load_mentee_preferences('mentee-preferences-cleaned.csv')
    mentors, code_to_mentors = load_mentors('mentor-project-code.csv')
    print(f"Loaded {len(mentees)} mentees, {len(mentors)} mentors, {len(code_to_mentors)} codes")
    assignments, flow, cost, mentees, mentor_list = build_and_solve(mentees, mentors, code_to_mentors, prefer_costs=(0,10,20,30,40), penalty_new_code=0.5)
    print(f"Flow assigned: {flow} mentees. Total cost: {cost}")
    write_results(mentees, assignments, 'allocations_mincost.csv')
    print('Wrote allocations_mincost.csv')

if __name__ == '__main__':
    main()
