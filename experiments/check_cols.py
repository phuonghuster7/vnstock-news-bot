import pickle
pred = pickle.load(open("results/v3/pred.pkl", "rb"))
print(pred.columns)
print(pred.head())
