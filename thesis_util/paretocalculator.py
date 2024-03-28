costa = 421.55
costb = 0.0086
import matplotlib.pyplot as plt
import numpy as np
def graph(formula, x_range,k):  
    x = np.array(x_range)
    #^ use x as range variable
    y = formula(x)
    #^          ^call the lambda expression with x
    #| use y as function result
    
    plt.xlabel("Aggregation group (s)")
    plt.ylabel("Batch size")
    plt.title(f"Each node has {k} layers")
    plt.plot(x,y)  
    plt.savefig(f"LLAMA_{k}.png")
    plt.close()
# solve costa * k * s = 2 * costb * batchsize
# solve (k*costa) / (2*costb)  = batchsize / s
for k in range(1,9):
    res = (k*costa) / (2*costb)
    print(k,res)
    graph(lambda x : x * res, range(1, 9), k)