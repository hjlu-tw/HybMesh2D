import sys, math, numpy as np
YTOP, YBOT, XL, XR = 0.344, -0.376, -0.079, 1.183
PXPERCHORD = 999.0          # fig6_top.png: the body is 999 px long (section 24b)
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
def inwin(q): return XL <= q[0] <= XR and YBOT <= q[1] <= YTOP
sags = []
for f in sorted(bodynodes):
    cands = [v for v in adj[f] if v not in bodynodes]
    if not cands: continue
    cur, prev = min(cands, key=lambda v: np.linalg.norm(pts[v]-pts[f])), f
    d = pts[cur]-pts[prev]; d = d/np.linalg.norm(d)
    poly = [pts[prev], pts[cur]]
    n = 0
    while n < 600:
        if cur in outer or not inwin(pts[cur]): break
        nxt = [v for v in adj[cur] if v != prev]
        if not nxt: break
        best, bd = None, -2
        for v in nxt:
            e = pts[v]-pts[cur]; nn = np.linalg.norm(e)
            if nn == 0: continue
            dot = float(np.dot(e/nn, d))
            if dot > bd: best, bd = v, dot
        if best is None or bd < 0.2 or not inwin(pts[best]): break
        e = pts[best]-pts[cur]; e = e/np.linalg.norm(e)
        poly.append(pts[best]); d, prev, cur, n = e, cur, best, n+1
    if n < 3: continue
    P = np.array(poly); a0, a1 = P[0], P[-1]
    v = a1 - a0; L = np.linalg.norm(v)
    if L == 0: continue
    nrm = np.array([-v[1], v[0]]) / L
    sags.append(float(np.abs((P - a0) @ nrm).max()))
a = np.array(sags) * PXPERCHORD
print("%-12s sagitta inside fig6's window: median %.2f px, p95 %.2f px, max %.2f px  (over %d lines)"
      % (sys.argv[1].split("/")[-2], np.median(a), np.percentile(a, 95), a.max(), len(a)))
