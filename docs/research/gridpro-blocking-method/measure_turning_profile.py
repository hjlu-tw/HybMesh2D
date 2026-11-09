import sys, math, numpy as np
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    return pts, cells
pts, cells = read(sys.argv[1])
adj, own = {}, {}
for ci, c in enumerate(cells):
    for t in range(len(c)):
        a, b = c[t], c[(t+1) % len(c)]
        adj.setdefault(a, set()).add(b); adj.setdefault(b, set()).add(a)
        own.setdefault((min(a,b), max(a,b)), []).append(ci)
bnd = [e for e, o in own.items() if len(o) == 1]
bnodes = {v for e in bnd for v in e}
body = [e for e in bnd if all(-0.05 <= pts[v][0] <= 1.05 and abs(pts[v][1]) < 0.12 for v in e)]
bodynodes = {v for e in body for v in e}
outer = bnodes - bodynodes
QS, bad = [[], [], [], []], 0
for f in sorted(bodynodes):
    cands = [v for v in adj[f] if v not in bodynodes]
    if not cands: continue
    cur, prev = min(cands, key=lambda v: np.linalg.norm(pts[v]-pts[f])), f
    d0 = (pts[cur]-pts[prev]); d0 = d0/np.linalg.norm(d0)
    d, steps, done = d0.copy(), [], False
    while len(steps) < 600:
        if cur in outer: done = True; break
        nxt = [v for v in adj[cur] if v != prev]
        if not nxt: break
        best, bd = None, -2
        for v in nxt:
            e = pts[v]-pts[cur]; nn = np.linalg.norm(e)
            if nn == 0: continue
            dot = float(np.dot(e/nn, d))
            if dot > bd: best, bd = v, dot
        if best is None or bd < 0.2: break
        e = pts[best]-pts[cur]; L = np.linalg.norm(e); e = e/L
        steps.append((math.degrees(math.acos(max(-1, min(1, float(np.dot(e, d)))))), L))
        d, prev, cur = e, cur, best
    if not done or not steps: bad += 1; continue
    tot = sum(L for _, L in steps)
    acc, q = 0.0, [0.0, 0.0, 0.0, 0.0]
    for ang, L in steps:
        frac = acc/tot
        q[min(3, int(frac*4))] += ang
        acc += L
    for i in range(4): QS[i].append(q[i])
name = sys.argv[1].split("/")[-2]
print("%-14s %d lines (%d failed).  turning accumulated in each QUARTER of the line:" % (name, len(QS[0]), bad))
print("                 wall->25%%   25-50%%     50-75%%    75%%->outer   (median deg)")
print("                 %7.2f   %7.2f   %7.2f   %7.2f"
      % tuple(float(np.median(np.array(q))) for q in QS))
print("                 %7.2f   %7.2f   %7.2f   %7.2f   (p95)"
      % tuple(float(np.percentile(np.array(q), 95)) for q in QS))
