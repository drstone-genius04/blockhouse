Smart Order Router – Cont & Kukanov Model

This project is a simulation of a Smart Order Router (SOR) designed to split a large buy order—specifically 5,000 shares—across several trading venues in a cost-effective way. The routing logic is based on a simplified version of the static cost model introduced in the paper:

"Optimal Order Placement in Limit Order Markets" by Cont & Kukanov (2014)

Code Overview

backtest.py: Main script that loads market data, runs the allocator, evaluates performance, and prints a summary of results as a JSON object. It uses only standard Python libraries along with numpy, pandas, and matplotlib.

allocate(): Implements the core optimization routine from the provided pseudocode. It searches all valid ways to split shares (in 100-share chunks) across venues and selects the allocation with the lowest expected cost.

compute_cost(): Calculates the cost of a given allocation, accounting for execution price, fees, rebates, and penalties for under- or overfilling the order.

run_backtest(): Replays a stream of market snapshots, applying the allocator at each step and simulating the resulting fills and spend.

baseline_best_ask(), baseline_twap(), baseline_vwap(): Implements three standard benchmarks used to compare the allocator's performance.

Parameter Search

To tune the allocator, we search over combinations of penalty parameters:

lambda_over: [0.1, 1, 10] — cost for buying more than the target

lambda_under: [0.1, 1, 10] — cost for underfilling the order

theta_queue: [0.0] — no queue risk applied due to missing queue position data

Each parameter combination is tested, and the one that results in the lowest total cost is selected.

Output Format

The script prints one JSON object at the end. It includes:

The best parameter values found

Total spend and average price using the optimized allocator

Comparison with three baselines: Best-Ask, 60-second TWAP, and VWAP

Basis-point savings vs. each baseline

A cumulative cost plot is also saved as results.png, showing how cost accumulates over time during execution.

Future Improvement Idea

Right now, the model assumes that all displayed shares in the order book can be filled, which isn’t always true in real trading. A useful improvement would be to simulate fill uncertainty based on queue position. For example, orders placed deeper in the book might have lower fill probabilities, which could be estimated using cancellation rates or modeled as a Poisson process. This would make the backtest more realistic by accounting for execution risk.

