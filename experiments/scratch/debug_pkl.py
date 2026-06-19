import pickle
with open("results/v8/pred.pkl", "rb") as f:
    p = pickle.load(f)
print("Type:", type(p))
if hasattr(p, "index"):
    print("Index names:", p.index.names)
if hasattr(p, "columns"):
    print("Columns:", p.columns)
if hasattr(p, "head"):
    print(p.head())
else:
    print(str(p)[:500])
