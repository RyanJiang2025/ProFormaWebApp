import numpy as np
import scipy
print(np.__version__)
print(scipy.__version__)

import sys
print(sys.executable)

import scipy
print(scipy.__version__)

import sys
print(sys.executable)

import numpy as np
from scipy.optimize import linprog

def maximize_utility(util_1, total_budget):
    """
    Solves utility maximization with linear preferences and budget constraint.
    """

    if not (0 <= util_1 <= 1):
        raise ValueError("util_1 must be between 0 and 1.")

    util_2 = 1 - util_1

    # Objective function: maximize U = util_1*x1 + util_2*x2 → minimize -U
    c = [-util_1, -util_2]

    # Budget constraint: x1 + x2 ≤ total_budget
    A_ub = [[1, 1]]
    b_ub = [total_budget]

    # Non-negativity constraints
    bounds = [(0, None), (0, None)]

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')

    if result.success:
        x1, x2 = result.x
        utility = util_1 * x1 + util_2 * x2
        return {
            "x1": x1,
            "x2": x2,
            "utility": utility
        }
    else:
        raise RuntimeError("Optimization failed:", result.message)

print(maximize_utility(util_1=0.7, total_budget=10))

test_cases = [
    {"util_1": 0.0, "total_budget": 10},   # All utility from good 2
    {"util_1": 1.0, "total_budget": 10},   # All utility from good 1
    {"util_1": 0.5, "total_budget": 10},   # Indifferent case
    {"util_1": 0.9, "total_budget": 1},    # Small budget, strong preference
    {"util_1": 0.1, "total_budget": 1},    # Small budget, weak preference
    {"util_1": 0.75, "total_budget": 100}, # Strong preference, large budget
    {"util_1": 0.25, "total_budget": 100}, # Opposite bias, large budget
    {"util_1": 0.6, "total_budget": 0.5},  # Very small budget
    {"util_1": 0.4, "total_budget": 1e6},  # Huge budget, low preference
    {"util_1": 0.6, "total_budget": 7.7},  # Arbitrary float budget
]

for i, case in enumerate(test_cases, 1):
    try:
        result = maximize_utility(case["util_1"], case["total_budget"])
        assert all(k in result for k in ['x1', 'x2', 'utility']), "Missing keys in result"
        print(f"Test {i}: util_1={case['util_1']}, budget={case['total_budget']}")
        print(f"  x1 = {result['x1']:.4f}, x2 = {result['x2']:.4f}, utility = {result['utility']:.4f}")
        print("-" * 60)
    except Exception as e:
        print(f"Test {i} FAILED: util_1={case['util_1']}, budget={case['total_budget']}")
        print(f"  Error: {e}")
        print("-" * 60)
