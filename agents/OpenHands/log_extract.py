import sys
import os
import numpy as np 

log_path = '/mydata/openhands/OpenHands/logs_sonnet'
log_files = [f for f in os.listdir(log_path) if f.endswith('.log')]
log_files.sort()
print(log_files)

cost_list = []
step_list = []
old_cost = 0
old_step = 0
db_map = dict()
for log_file in log_files:

    log_file_path = os.path.join(log_path, log_file)

    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                if 'Accumulated cost:' in line:
                    l = line.strip()
                    price = float(l.split(' ')[-1])
                    if price < old_cost:
                       cost_list.append(old_cost)
                       old_cost = price
                    else:
                       old_cost = price
                if 'Step:' in line:
                    l = line.strip()
                    try:
                        step = int(l.split(' ')[-1])
                    except:
                        test = 1
                    if step < old_step:
                        step_list.append(old_step)
                        old_step = step
                    else:
                        old_step = step
                if 'Finished evaluation for instance ' in line:
                    db = line.split('Finished evaluation for instance ')[1].split(':')[0]
                    db_map[db] = {'cost': old_cost, 'step': old_step}
                    
                  
    except:
        print(f"File not found: {log_file_path}")
        # continue
        sys.exit(1)
cost_list.append(old_cost)
step_list.append(old_step)
print(cost_list)
print(step_list)
print(len(cost_list))
print(len(step_list))
print(sum(cost_list) / len(cost_list))
print(sum(step_list) / len(step_list))
print(db_map)

count = [k['cost'] for db, k in db_map.items()]

step = [k['step'] for db, k in db_map.items()]
print(len(count))
print(np.mean(count))
print(np.mean(step))