from vnstock import Quote
import pandas as pd

q = Quote(symbol="ACB")
df = q.history(length="6M", interval="1D")
print("ACB Data length:", len(df))
print(df.head())
print(df.tail())
print("Data types:")
print(df.dtypes)
