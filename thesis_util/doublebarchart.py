import matplotlib.pyplot as plt  
import numpy as np
plt.figure(figsize =(10, 7))
plt.rcParams.update({'font.size': 18})

# X = ['Test 1','Test 2','Test 3','Test 4','Test 5'] 
# Optimal = [0.1765983464,0.1532256771,0.147316161,0.1813132563,0.04769409057] 
# Chosen = [0.1379193849,0.103866531,0.1449902759,0.1780318895,0.04371227986] 
# Optimal_var = [0.005993914099, 0.0027967284,0.006997761195,0.006188673643,0.0007337142186]
# Chosen_var = [0.007287966984,0.002920502568,0.00686414032,0.006117933195,0.000771218473]


X = ['Test 7','Test 8','Test 9','Test 10'] 
Optimal = [0.2802749593,0.2646416621,0.4603779043,0.2502311321] 
Chosen = [0.2093647101,0.225523272,0.1537496388,0.2147039005] 
Optimal_var = [0.006407396306,0.001814693546,0.02043424581,0.001254727233]
Chosen_var = [0.01122325625,0.008184365997,0.02252080459,0.007126924601]
X_axis = np.arange(len(X)) 
  
plt.bar(X_axis - 0.2, Optimal, 0.4, label = 'Optimal') 
plt.bar(X_axis + 0.2, Chosen, 0.4, label = 'Chosen') 
plt.errorbar(X_axis - 0.2, Optimal, Optimal_var, fmt='.', color='Black')
plt.errorbar(X_axis + 0.2, Chosen, Chosen_var, fmt='.', color='Black')
plt.xticks(X_axis, X) 

plt.ylabel("Proportion Improvement of Cost per Batch") 
plt.title("Results of addition of 5 nodes") 
plt.legend() 
plt.show()