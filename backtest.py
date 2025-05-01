import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from itertools import product
from datetime import datetime, timedelta

# === Load and preprocess data ===
df = pd.read_csv("l1_day.csv")
df = df[['ts_event', 'publisher_id', 'ask_px_00', 'ask_sz_00']]
df_sorted = df.sort_values(by='ts_event')
df_unique = df_sorted.drop_duplicates(subset=['ts_event', 'publisher_id'], keep='first')
snapshots = list(df_unique.groupby('ts_event'))[::5]  # Downsample every 5th snapshot

# === Venue class ===
class Venue:
    def __init__(self, ask, ask_size, fee=0.0, rebate=0.0):
        self.ask = ask
        self.ask_size = ask_size
        self.fee = fee
        self.rebate = rebate

# === Allocator from pseudocode ===
def allocate(order_size, venues, λo, λu, θ):
    step = 100
    splits = [[]]
    for v in range(len(venues)):
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, venues[v].ask_size)
            for q in range(0, max_v + 1, step):
                new_splits.append(alloc + [q])
        splits = new_splits

    best_cost = float('inf')
    best_split = []
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues, order_size, λo, λu, θ)
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    return best_split, best_cost

def compute_cost(split, venues, order_size, λo, λu, θ):
    executed = 0
    cash_spent = 0.0
    for i in range(len(venues)):
        exe = min(split[i], venues[i].ask_size)
        executed += exe
        cash_spent += exe * (venues[i].ask + venues[i].fee)
        rebate = max(split[i] - exe, 0) * venues[i].rebate
        cash_spent -= rebate
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    return cash_spent + λu * underfill + λo * overfill + θ * (underfill + overfill)

# === Backtest Engine ===
def run_backtest(snapshots, order_size, λo, λu, θ, track=False):
    remaining = order_size
    spent = 0.0
    cumulative = []
    for ts, snapshot in snapshots:
        venues = [Venue(row['ask_px_00'], int(row['ask_sz_00'])) for _, row in snapshot.iterrows()
                  if not pd.isna(row['ask_px_00']) and row['ask_sz_00'] > 0][:4]
        if not venues or remaining <= 0:
            continue
        try:
            alloc, _ = allocate(min(remaining, order_size), venues, λo, λu, θ)
        except:
            continue
        for i, venue in enumerate(venues):
            fill = min(alloc[i], venue.ask_size) if i < len(alloc) else 0
            spent += fill * venue.ask
            remaining -= fill
            if track:
                cumulative.append(spent)
            if remaining <= 0:
                break
    return spent, spent / order_size, cumulative

# === Baseline Strategies ===
def baseline_best_ask(snapshots, order_size):
    remaining, spent = order_size, 0.0
    for ts, snapshot in snapshots:
        if remaining <= 0: break
        best_row = snapshot.loc[snapshot['ask_px_00'].idxmin()]
        px, sz = best_row['ask_px_00'], int(best_row['ask_sz_00'])
        fill = min(sz, remaining)
        spent += fill * px
        remaining -= fill
    return spent, spent / order_size

def baseline_twap(snapshots, order_size):
    interval = timedelta(seconds=60)  # As per task spec
    share = order_size // 10
    remaining, spent = order_size, 0.0
    last_ts = None
    total_filled = 0
    for ts_str, snapshot in snapshots:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if last_ts is None or (ts - last_ts) >= interval:
            if snapshot.empty: continue
            best_row = snapshot.loc[snapshot['ask_px_00'].idxmin()]
            px, sz = best_row['ask_px_00'], int(best_row['ask_sz_00'])
            fill = min(sz, min(remaining, share))
            spent += fill * px
            total_filled += fill
            remaining -= fill
            last_ts = ts
        if remaining <= 0: break
    avg_price = spent / total_filled if total_filled > 0 else 0.0
    return spent, avg_price

def baseline_vwap(snapshots, order_size):
    remaining, spent = order_size, 0.0
    for ts, snapshot in snapshots:
        if remaining <= 0: break
        total_sz = snapshot['ask_sz_00'].sum()
        if total_sz == 0: continue
        for _, row in snapshot.iterrows():
            weight = row['ask_sz_00'] / total_sz
            qty = int(weight * order_size)
            fill = min(qty, int(row['ask_sz_00']), remaining)
            spent += fill * row['ask_px_00']
            remaining -= fill
            if remaining <= 0: break
    return spent, spent / order_size

# === Grid Search + Evaluation ===
ORDER_SIZE = 1000
param_grid = list(product([0.1, 1, 10], repeat=2))
best = (None, float('inf'), 0)
for λo, λu in param_grid:
    spent, avg, _ = run_backtest(snapshots, ORDER_SIZE, λo, λu, 0.0)
    if spent < best[1]:
        best = ((λo, λu, 0.0), spent, avg)

λo, λu, θ = best[0]
spent, avg, cumulative = run_backtest(snapshots, ORDER_SIZE, λo, λu, θ, track=True)
b1, a1 = baseline_best_ask(snapshots, ORDER_SIZE)
b2, a2 = baseline_twap(snapshots, ORDER_SIZE)
b3, a3 = baseline_vwap(snapshots, ORDER_SIZE)

summary = {
    "best_params": {"lambda_over": λo, "lambda_under": λu, "theta_queue": θ},
    "total_spent": spent,
    "avg_fill_price": avg,
    "baseline_best_ask": {"total_spent": b1, "avg_fill_price": a1},
    "baseline_twap": {"total_spent": b2, "avg_fill_price": a2},
    "baseline_vwap": {"total_spent": b3, "avg_fill_price": a3},
    "savings_vs_best_ask_bps": 10000 * (b1 - spent) / b1 if b1 > 0 else None,
    "savings_vs_twap_bps": 10000 * (b2 - spent) / b2 if b2 > 0 else None,
    "savings_vs_vwap_bps": 10000 * (b3 - spent) / b3 if b3 > 0 else None
}

# === Save JSON output ===
with open("results.json", "w") as f:
    json.dump(summary, f, indent=2)

# === Save cost chart ===
plt.figure(figsize=(8, 4))
plt.plot(cumulative, label="Cumulative Spend")
plt.xlabel("Snapshots")
plt.ylabel("Cash Spent ($)")
plt.title("Cumulative Cost of Optimal Strategy")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("results.png")
plt.show()

# Print final JSON
print(json.dumps(summary, indent=2))
