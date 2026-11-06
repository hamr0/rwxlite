"""Round 13 cost-sensitive term (R13-L3). Added to the recipe's loss; the recipe itself is untouched.
  cost(truth t, predicted letter j) = loose_cost if j < t (too loose: below the truth), 1 if j > t (too tight), 0 if j == t. Letter order r=0 < w=1 < x=2.
  term = mean over rows of  sum_j p_j * cost(t, j),  p = softmax(logits), t = the row's HARD label y (for soft-target rows too: the v4 hard label).
  loss = base_loss + term.   loose_cost = 0 means off (finetune.py does not call this)."""
import torch

def cost_matrix(loose_cost):
    C = torch.zeros(3, 3)
    for t in range(3):
        for j in range(3):
            C[t, j] = loose_cost if j < t else (1.0 if j > t else 0.0)
    return C

def expected_cost(logits, y, loose_cost):
    return (torch.softmax(logits, -1) * cost_matrix(loose_cost)[y]).sum(1).mean()
