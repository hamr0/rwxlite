"""python3 train/test_losscost.py : a too-loose prediction must cost more than an equally confident too-tight one."""
import sys, os
sys.path.append(os.path.expanduser('~/.local/lib/python3.14/site-packages')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import torch
from losscost import expected_cost
def lg(letter, conf=0.9):
    p = torch.full((1, 3), (1 - conf) / 2); p[0, letter] = conf; return p.log()
for t, loose, tight in ((1, 0, 2), (2, 1, None), (2, 0, None), (1, 0, 2)):
    if tight is None: continue
    y = torch.tensor([t])
    a, b = expected_cost(lg(loose), y, 3).item(), expected_cost(lg(tight), y, 3).item()
    assert a > b, (t, a, b)                      # truth w: predicted r (loose) > predicted x (tight)
y = torch.tensor([2]); assert expected_cost(lg(1), y, 3) > expected_cost(lg(2), y, 3)   # truth x: w costs more than x
y = torch.tensor([0]); assert expected_cost(lg(2), y, 3) > 0                              # truth r: nothing below, x costs 1 per mass
assert abs(expected_cost(lg(1, 1 - 1e-9), torch.tensor([1]), 3).item()) < 1e-6           # exact = zero cost
p_loose = expected_cost(lg(0, 1 - 1e-9), torch.tensor([1]), 3).item(); p_tight = expected_cost(lg(2, 1 - 1e-9), torch.tensor([1]), 3).item()
assert abs(p_loose / p_tight - 3) < 1e-3, (p_loose, p_tight)                              # exactly 3x
print('ok: too-loose costs', round(p_loose, 3), 'vs too-tight', round(p_tight, 3))
