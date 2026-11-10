import json, os, sys
T = os.environ["CLAUDE_JOB_DIR"] + "/tmp"
xT, yT, xR, yR, yL = map(float, sys.argv[1:6])
d = {"format_version": 1,
 "corners": [{"id": i, "kind": "free", "xy": xy} for i, xy in (
   ("w0",[0.0,0.0]), ("w1",[xT,0.0]), ("w2",[xR,0.0]),
   ("T", [xT,yT]), ("l0",[0.0,yT]), ("l1",[0.0,yL]), ("r1",[xR,yR]))],
 "edges": [
   {"id":"b_s","corners":["w0","w1"],"kind":"wall","count":17},
   {"id":"b_e","corners":["w1","T"], "kind":"interface","count":5},
   {"id":"b_n","corners":["l0","T"], "kind":"interface"},
   {"id":"b_w","corners":["w0","l0"],"kind":"wall"},
   {"id":"a_e","corners":["T","r1"], "kind":"interface"},
   {"id":"a_n","corners":["l1","r1"],"kind":"wall"},
   {"id":"a_w","corners":["l0","l1"],"kind":"wall","count":5},
   {"id":"c_s","corners":["w1","w2"],"kind":"wall"},
   {"id":"c_e","corners":["w2","r1"],"kind":"wall"}],
 "blocks": [
   {"id":"b","edges":["b_s","b_e","b_n","b_w"]},
   {"id":"a","edges":["b_n","a_e","a_n","a_w"]},
   {"id":"c","edges":["c_s","c_e","a_e","b_e"]}]}
json.dump(d, open(T + "/nest.json","w"), indent=1)
