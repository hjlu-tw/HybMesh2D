"""WHERE along a wall-normal grid line its turning happens, and HOW MUCH in total.

    python3 docs/research/gridpro-blocking-method/measure_turning_profile.py <mesh.vtk>...

Walks each line from the body outward, always taking the straightest continuation,
and TERMINATES at the outer boundary -- reporting how many lines fail to reach it,
which is the control S27a added after the first version turned onto the outer
boundary and kept walking. Per line it reports the turning accumulated in each
quarter of that line's own arc length (S28a's instrument) AND the per-line total
(S27a's), median / p95 / max.

The quarter split and the total answer different questions and S27/S28 both needed
both: two meshes with the same total can put it all against the wall or spread it
evenly out to the boundary, and that difference is the whole of S28a.

NOTE the body is detected GEOMETRICALLY, as a boundary edge with both ends inside
x in [-0.05, 1.05] and |y| < 0.12. That is this repo's aerofoil and nothing else.
"""
import sys, math, numpy as np
def read(p):
    tok = open(p).read().split()
    i = tok.index("POINTS"); n = int(tok[i+1])
    pts = np.array(tok[i+3:i+3+3*n], float).reshape(n,3)[:,:2]
    j = tok.index("CELLS"); nc = int(tok[j+1]); k = j+3; cells=[]
    for _ in range(nc):
        m = int(tok[k]); cells.append([int(x) for x in tok[k+1:k+1+m]]); k += 1+m
    return pts, cells
def measure(path):
  pts, cells = read(path)
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
  QS, TOT, bad = [[], [], [], []], [], 0
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
      TOT.append(sum(a for a, _ in steps))
  return QS, TOT, bad


for path in sys.argv[1:]:
    # the last TWO components: the committed meshes are <case>/mesh.vtk, where
    # the parent is the name, but a scratch file is <dir>/<case>.vtk, where it
    # is the basename -- printing only one of them labelled five cases "tmp"
    name = "/".join(path.split("/")[-2:]).replace(".vtk", "")
    QS, TOT, bad = measure(path)
    print("%-34s %d lines (%d failed to reach the outer boundary)." % (name, len(QS[0]), bad))
    if not TOT:
        print("   no line reached the outer boundary, so there is nothing to report")
        continue
    t = np.array(TOT)
    print("   TOTAL per line:   median %6.2f   p95 %6.2f   max %6.2f  (deg)"
          % (float(np.median(t)), float(np.percentile(t, 95)), float(t.max())))
    print("                 wall->25%%   25-50%%     50-75%%    75%%->outer   (median deg)")
    print("                 %7.2f   %7.2f   %7.2f   %7.2f"
          % tuple(float(np.median(np.array(q))) for q in QS))
    print("                 %7.2f   %7.2f   %7.2f   %7.2f   (p95)"
          % tuple(float(np.percentile(np.array(q), 95)) for q in QS))
