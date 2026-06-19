import pickle
v4 = pickle.load(open("results/v4/pred.pkl", "rb"))
v8 = pickle.load(open("results/v8/pred.pkl", "rb"))
print("v4 shape:", v4.shape)
print("v8 shape:", v8.shape)
print("v4 index:", v4.index)
print("v8 index:", v8.index)
