from vnstock import Listing
listing = Listing()
print("Listing dir:", [x for x in dir(listing) if not x.startswith("_")])
try:
    companies = listing.companies()
    print("Companies columns:", companies.columns.tolist())
    print(companies.head(2))
except Exception as e:
    print("companies() error:", e)
