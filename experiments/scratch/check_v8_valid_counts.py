import pickle
v8 = pickle.load(open("results/v8/pred.pkl", "rb"))
daily_counts = v8.groupby(level="datetime").apply(lambda g: len(g.dropna()))
print("Daily valid predictions counts (min, max, mean):", daily_counts.min(), daily_counts.max(), daily_counts.mean())
print("Zero counts days count:", (daily_counts == 0).sum())
print("Less than 5 predictions days count:", (daily_counts < 5).sum())
