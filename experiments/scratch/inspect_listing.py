import vnstock
import inspect
print("vnstock version:", getattr(vnstock, '__version__', 'unknown'))
print("Listing signature:", inspect.signature(vnstock.Listing))
print("Listing doc:", vnstock.Listing.__doc__)
