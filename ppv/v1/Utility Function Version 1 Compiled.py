import numpy as np
import scipy
import random
import pandas as pd

seed_for_prng = 78557
prng = np.random.default_rng(seed_for_prng)

from scipy.optimize import minimize

def ces_utility(y, alpha, rho):
    y = np.array(y)
    
    # Disallow negative quantities
    if np.any(y < 0):
        return -np.inf
    
    # Guard against undefined behavior when rho < 0 and y == 0
    if rho < 0 and np.any(y == 0):
        return -np.inf
    
    if np.isclose(rho, 0.0):
        # Cobb-Douglas limit
        return np.prod(y ** alpha)
    else:
        return (np.sum(alpha * y**rho))**(1/rho)

def maximize_ces_n_goods(alpha, rho, budget):
    alpha = np.array(alpha)
    n = len(alpha)
    
    # Normalization check
    if not np.isclose(np.sum(alpha), 1.0):
        raise ValueError("Weights alpha must sum to 1.")
    
    # All prices = 1 by assumption
    prices = np.ones(n)
    
    def objective(y):
        return -ces_utility(y, alpha, rho)
    
    # Budget constraint (equality, since CES utility is monotonic)
    constraints = [{'type': 'eq', 'fun': lambda y: budget - np.sum(prices * y)}]
    
    # Non-negativity bounds
    bounds = [(0, None) for _ in range(n)]
    
    # Improved starting point based on alpha (p_i = 1)
    y0 = budget * alpha

    result = minimize(objective, y0, bounds=bounds, constraints=constraints)

    if result.success:
        y_opt = result.x
        utility = ces_utility(y_opt, alpha, rho)
        return {
            'quantities': y_opt,
            'utility': utility
        }
    else:
        raise RuntimeError("Optimization failed: " + result.message)

def matrix_value_call(voter, policy, called_matrix): #calls specific values within any matrix. Note: this is zero indexed
    return called_matrix.iloc[voter, policy]

def complete_preference_calculator ():
    complete_preference_matrix = np.zeros((num_voters, num_voters, num_policies))
    for p in range(num_policies):
        for i in range(num_voters):
            for j in range(num_voters):
                complete_preference_matrix[i, j, p] = 5 - np.abs(matrix_value_call(i, p, preference_matrix) - (matrix_value_call(j,p,preference_matrix))) #for a specific policy, if the alignment is exact, then value = 5. If it differs by 1 (i.e. 2 vs 3) then the alignment is 4.If they differ completely (1 vs 5) then the alignment is 1.
    return complete_preference_matrix

def simple_preference_calculator (big_pref_matrix): #takes the complete preference alignment matrix, which measures i x j preference alignment for every policy, and averages the values to generate a single number for i  j prefernce alignment
    simple_preference_matrix = np.zeros((num_voters, num_voters))
    for i in range(num_voters):
        for j in range(num_voters):
            simple_preference_matrix[i, j] = np.mean(big_pref_matrix[i, j, :])
    return simple_preference_matrix

def j_delegates_to_i (j, rho): #If we really wanted to be picky, then we could make every j voter have a different rho; if not we could just define it globally.
    #the CES function has inputs of alpha, rho, and budget. Rho = whatever, budget = 100. Thus alpha must be defined

    alpha_list = np.zeros(num_voters) #Since there are as many alpha values as goods/i voters (delegatees), we start by generating a blank list of n length
    for i in range(len(alpha_list)):
        alpha_list[i] = (simple_preference_alignment[i, j] + simple_voter_expertise[i]) #calculates the alpha of each voter i, or in other words, the attractiveness of delegating to them, which is a sum of preference alignment and expertise.
    alpha_list = alpha_list/np.sum(alpha_list) #Since our CES funcion requires that all alpha sum to 1, this normalizes our values
    return maximize_ces_n_goods (alpha_list, rho, 100) #maximizes CES function with alpha values (Preference alignment + expertise), rho (some value), and budget=100

def voter_to_voter_delegations (rho):
    delegation_utility_list = np.zeros(num_voters) #empty utility list
    n_x_n_matrix = np.array(j_delegates_to_i (0, rho)['quantities']).reshape(1, -1) #because we are using numpy array matrix, we have to first calculate the first j and then add onto that
    delegation_utility_list [0] = j_delegates_to_i (0, rho)['utility'] #Here we calculate the first j's delegations and utility

    for j in range(1, num_voters):
        new_row = np.array(j_delegates_to_i(j, rho)['quantities']).reshape(1, -1)
        n_x_n_matrix = np.vstack((n_x_n_matrix, new_row))
        delegation_utility_list[j] = j_delegates_to_i(j, rho)['utility']
    return {
            'delegation_matrix': n_x_n_matrix,
            'utility': delegation_utility_list
        }

def j_delegates_to_p (j, rho): #Similar framework for j_delegates_to_i, but with policy factors
    alpha_list = preference_matrix.iloc[j] #Our alphas for voter j are just their policy preferences for all policy p, which is already contained in voter j's row in our preference_matrix
    alpha_list = alpha_list/np.sum(alpha_list) #Since our CES funcion requires that all alpha sum to 1, this normalizes our values
    return maximize_ces_n_goods (alpha_list, rho, 100) #maximizes CES function with alpha values, rho (some value), and budget=100

def voter_to_policy_delegations (rho):
    delegation_utility_list = np.zeros(num_voters) #empty utility list
    n_x_p_matrix = np.array(j_delegates_to_p (0, rho)['quantities']).reshape(1, -1) #First j's policy delegations
    delegation_utility_list [0] = j_delegates_to_p (0, rho)['utility'] #Here we calculate the first j's delegations and utility

    for j in range(1, num_voters): #CHANGE HERE TO SOLVE INCOMPATIBILITIES
        new_row = np.array(j_delegates_to_p(j, rho)['quantities']).reshape(1, -1)
        n_x_p_matrix = np.vstack((n_x_p_matrix, new_row))
        delegation_utility_list[j] = j_delegates_to_p(j, rho)['utility']
    return {
            'delegation_matrix': n_x_p_matrix,
            'utility': delegation_utility_list
        }

def normalize_full_delegation_matrix():
    for j in range(num_voters):
        for p in range(num_voters, num_voters+num_policies):
            full_delegation_matrix[p, j] = full_delegation_matrix[p, j]/100 * full_delegation_matrix[j,j]
        full_delegation_matrix[j, j] = 0
    


################################################################



print("Starting Variables")
#How many voters?
num_voters = 3
print("Number of voters: ", num_voters)

#How many policies?
num_policies = 4
print("Number of policies: ", num_policies)

rho = 0.5
print("rho = ", rho)
print()

expertise_matrix = pd.DataFrame(
    prng.integers(1, 6, size = (num_voters, num_policies)),
    columns = [f"policy_{i}" for i in range(num_policies)],
    index = [f"voter_{i}" for i in range(num_voters)])

simple_voter_expertise = np.zeros(num_voters) #simplifies our expertise matrix, which used to be by policy, into a single value
for i in range(num_voters):
    simple_voter_expertise[i] = np.mean(expertise_matrix.iloc[i])

preference_matrix = pd.DataFrame(
    prng.integers(1, 6, size = (num_voters, num_policies)),
    columns = [f"policy_{i}" for i in range(num_policies)],
    index = [f"voter_{i}" for i in range(num_voters)])

complete_preference_alignment = complete_preference_calculator()

simple_preference_alignment = simple_preference_calculator (complete_preference_alignment)

voter_to_voter_matrix = np.transpose(voter_to_voter_delegations(rho)['delegation_matrix']) #This calls the function from section 4 and assigns it to a variable. Nothing special.
voter_to_voter_utility = voter_to_voter_delegations(rho)['utility']

voter_to_policy_matrix = np.transpose(voter_to_policy_delegations(rho)['delegation_matrix'])
voter_to_policy_utility = voter_to_policy_delegations(rho)['utility']

policy_to_voter_matrix = np.zeros((num_voters, num_policies))
policy_to_policy_matrix = np.identity((num_policies))*100

full_delegation_matrix = np.block([
    [voter_to_voter_matrix, policy_to_voter_matrix],
    [voter_to_policy_matrix, policy_to_policy_matrix] 
])

normalize_full_delegation_matrix()

full_delegation_matrix = full_delegation_matrix/100 #this is mainly just to normalize the whole thing so that everything is in percentages

np.set_printoptions(precision=5, suppress=True) #limits decimals for neatness
print("Full final delegation matrix: ")
print(full_delegation_matrix)