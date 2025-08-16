import json
import os
import re


costs = []
steps = []
db = os.listdir("logs_claude35")
db.sort()
for file in db:
    step = 0
    with open(f"logs_claude35/{file}", "r") as f:
        for line in f.readlines():
            if "Final Cost og augment agent:" in line:
                cost = re.search(r"Final Cost og augment agent: (\d+\.\d+)", line).group(1)
                costs.append(float(cost))
            if 'NEW TURN:' in line:
                step= int(re.search(r"NEW TURN: (\d+)", line).group(1))
    steps.append(step)
                
print(costs)
print(len(costs))
print(sum(costs) / len(costs))
print(steps)
print(len(steps))
print(sum(steps) / len(steps))