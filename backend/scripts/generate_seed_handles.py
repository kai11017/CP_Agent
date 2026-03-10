import requests
import json
import random 
from collections import defaultdict

BUCKETS = [
    (800, 999),
    (1000, 1199),
    (1200, 1399),
    (1400, 1599),
    (1600, 1799),
    (1800, 1999),
    (2000, 2199)
]

users= requests.get("https://codeforces.com/api/user.ratedList").json()["result"]

bucket_users= defaultdict(list)

for user in users:
    rating=user.get("rating",0)
    handle=user["handle"]

    for low,high in BUCKETS:
        if low<=rating<=high:
            bucket_users[(low,high)].append(handle)

for (low,high),handles in bucket_users.items():
    selected=random.sample(handles,min(40,len(handles)))
    filename=f"benchmark_seed/{low}_{high}.json"

    with open(filename,"w") as f:
        json.dump(selected,f,indent=2)

print("Seed handles generated.")        
 

 ## now that i ahve genrated the dataset ,i dont have tu run it again