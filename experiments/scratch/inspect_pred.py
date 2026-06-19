import pickle
import pandas as pd

v8_path = "results/v8/pred.pkl"
with open(v8_path, "rb") as f:
    df = pickle.load(f)
print("Head:")
print(df.head())
print("Tail:")
print(df.tail())
print("Columns:", df.columns)
print("Shape:", df.shape)
