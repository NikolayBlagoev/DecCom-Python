import matplotlib.pyplot as plt
# from: https://www.geeksforgeeks.org/box-plot-in-python-using-matplotlib/
data_1 = [100*(386 - 386)/386, 100*(386 - 386)/386, 100*(402 - 386)/386, 100*(389 - 386)/386, 100*(391 - 386)/386, 100*(387 - 386)/386,
 100*(354 - 386)/386,  100*(402 - 386)/386, 100*(389 - 386)/386, 100*(387 - 386)/386]

data_2 = [100*(17292 - 17292)/17292, 100*(17536 - 17292)/17292, 100*(17675 - 17292)/17292, 100*(17671 - 17292)/17292, 100*(17905 - 17292)/17292, 100*(18406 - 17292)/17292,
 100*(17675 - 17292)/17292,  100*(18848 - 17292)/17292, 100*(17811 - 17292)/17292, 100*(18007.0 - 17292)/17292]
fig = plt.figure(figsize =(10, 7))

plt.rcParams.update({'font.size': 18})
data = [data_1, data_2]
 
fig = plt.figure(figsize =(10, 7))
ax = fig.add_subplot(111)

bp = ax.boxplot(data, patch_artist = True,
                notch ='True', vert = 0)
 
colors = ['#0000FF', '#00FF00', '#FF00FF']
 
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
 
for whisker in bp['whiskers']:
    whisker.set(color ='#8B008B',
                linewidth = 1.5,
                linestyle =":")
 

for cap in bp['caps']:
    cap.set(color ='#8B008B',
            linewidth = 2)

for median in bp['medians']:
    median.set(color ='red',
               linewidth = 3)
 

for flier in bp['fliers']:
    flier.set(marker ='D',
              color ='#e7298a',
              alpha = 0.5)
     

ax.set_yticklabels(['Test 1', 'Test 2'])
 

plt.title("Difference from optimal flow")
 

ax.get_xaxis().tick_bottom()
ax.get_yaxis().tick_left()
     
# show plot
plt.show()