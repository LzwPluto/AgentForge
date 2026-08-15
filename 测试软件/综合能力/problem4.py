# -*- coding: utf-8 -*-
"""
2024国赛B题 问题4：次品率由抽样估计得到，重做问题2与问题3
思路：
  问题1已给出抽样方案：95%拒收情形 n=29（检出>=1件次品即拒收）。
  问题4中次品率未知，通过抽样观测获得点估计与置信区间。
  采用 Wilson score 区间估计 95% 置信区间。
  用 点估计、置信区间下界(乐观)、上界(悲观) 三种次品率，分别重跑问题2、3，
  检验决策方案的稳健性（若三种情形决策一致则稳健）。

抽样设定：
  设真实次品率为 p_true（问题2各情形的 p），抽 n=29 件，观测次品数 x=round(n*p_true)，
  得 p_hat=x/n，95% Wilson 区间 [p_low, p_high]。
"""

import math


# ---------- Wilson score 95% 置信区间 ----------
def wilson_ci(x, n, z=1.96):
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half


# ---------- 问题2 单个情形的求解（复用 problem2 模型） ----------
def solve_case(p1, c1, t1, p2, c2, t2, pf, ca, tf, s, L, r):
    best_X = float('inf')
    best = None
    for d1 in (0, 1):
        for d2 in (0, 1):
            for df in (0, 1):
                for dr in (0, 1):
                    for d1p in (0, 1):
                        for d2p in (0, 1):
                            P1 = (c1 + t1) / (1 - p1) if d1 else c1
                            P2 = (c2 + t2) / (1 - p2) if d2 else c2
                            g1 = 1.0 if d1 else (1 - p1)
                            g2 = 1.0 if d2 else (1 - p2)
                            P_good = g1 * g2 * (1 - pf)
                            P_bad = 1 - P_good
                            base = (P1 + P2) + ca + tf * df
                            L_m = L if df == 0 else 0.0
                            if dr == 0:
                                X = (base - P_good * s + P_bad * L_m) / P_good
                            else:
                                q1 = 0.0 if d1 else p1
                                q2 = 0.0 if d2 else p2
                                cost_rec1 = q1 * (c1 + t1) / (1 - p1) if d1p else 0.0
                                cost_rec2 = q2 * (c2 + t2) / (1 - p2) if d2p else 0.0
                                base_rec = (cost_rec1 + cost_rec2) + ca + tf * df + r
                                g1p = 1.0 if d1p else (1 - q1)
                                g2p = 1.0 if d2p else (1 - q2)
                                P_good_rec = g1p * g2p * (1 - pf)
                                P_bad_rec = 1 - P_good_rec
                                X_rec = (base_rec - P_good_rec * s + P_bad_rec * L_m) / P_good_rec
                                X = base - P_good * s + P_bad * L_m + P_bad * X_rec
                            if X < best_X:
                                best_X = X
                                best = (d1, d2, df, dr, d1p, d2p)
    return best, best_X


# ---------- 问题2 六种情形数据 ----------
scenarios = [
    dict(p1=0.10, c1=4, t1=2, p2=0.10, c2=18, t2=3, pf=0.10, ca=6, tf=3, s=56, L=6, r=5, label=1),
    dict(p1=0.20, c1=4, t1=2, p2=0.20, c2=18, t2=3, pf=0.20, ca=6, tf=3, s=56, L=6, r=5, label=2),
    dict(p1=0.10, c1=4, t1=2, p2=0.10, c2=18, t2=3, pf=0.10, ca=6, tf=3, s=56, L=30, r=5, label=3),
    dict(p1=0.20, c1=4, t1=1, p2=0.20, c2=18, t2=1, pf=0.20, ca=6, tf=2, s=56, L=30, r=5, label=4),
    dict(p1=0.10, c1=4, t1=8, p2=0.20, c2=18, t2=1, pf=0.10, ca=6, tf=2, s=56, L=10, r=5, label=5),
    dict(p1=0.05, c1=4, t1=2, p2=0.05, c2=18, t2=3, pf=0.05, ca=6, tf=3, s=56, L=10, r=40, label=6),
]

n_sample = 29  # 问题1情形(1)的最小样本量

print("=" * 80)
print("2024国赛B题 问题4：抽样估计次品率下的稳健决策（重做问题2）")
print("=" * 80)
print(f"抽样方案：随机抽取 n={n_sample} 件（问题1情形1最小样本量）")
print("次品率估计：Wilson 95% 置信区间")
print()

for sc in scenarios:
    label = sc['label']
    p_true = sc['p1']
    x = round(n_sample * p_true)
    p_hat = x / n_sample
    p_low, p_high = wilson_ci(x, n_sample)
    print(f"--- 情形{label}: 真实次品率={p_true:.0%}, 抽样观测次品数 x={x} "
          f"点估计 p_hat={p_hat:.4f}, 95%CI=[{p_low:.4f},{p_high:.4f}] ---")

    for tag, pe in [("乐观(下界)", p_low), ("点估计", p_hat), ("悲观(上界)", p_high)]:
        sc2 = dict(sc)
        sc2['p1'] = pe
        sc2['p2'] = pe
        sc2['pf'] = pe
        sc2.pop('label')
        best, X = solve_case(**sc2)
        d1, d2, df, dr, d1p, d2p = best
        print(f"  {tag:10s} p={pe:.4f}: X={X:8.4f}  决策(d1={d1},d2={d2},df={df},dr={dr},d1'={d1p},d2'={d2p})")
    print()


# ---------- 问题3 用点估计与区间上下界重跑 ----------
def part_supply(pid, p, c, t, inspect):
    if inspect:
        return (c + t) / (1 - p), 1.0
    else:
        return c, 1 - p


def node_cost(children, p_node, ca, t_node, r_node, is_final=False):
    best_cost = float('inf')
    best_decision = None
    for inspect in (0, 1):
        for dismantle in (0, 1):
            if dismantle and r_node is None:
                continue
            child_cost = sum(c for c, _ in children)
            child_good = 1.0
            for _, g in children:
                child_good *= g
            P_good = child_good * (1 - p_node)
            P_bad = 1 - P_good
            base = child_cost + ca + (t_node if inspect else 0)
            if is_final:
                L_m = L_final if not inspect else 0
                if dismantle:
                    rec_child_cost = child_cost
                    rec_base = rec_child_cost + ca + (t_node if inspect else 0)
                    rec_P_good = child_good * (1 - p_node)
                    rec_P_bad = 1 - rec_P_good
                    X_rec = (rec_base + r_node - rec_P_good * s_f + rec_P_bad * L_m) / rec_P_good
                    X = base - P_good * s_f + P_bad * L_m + P_bad * X_rec
                else:
                    X = (base - P_good * s_f + P_bad * L_m) / P_good
            else:
                if dismantle:
                    rec_child_cost = child_cost
                    rec_base = rec_child_cost + ca + (t_node if inspect else 0) + r_node
                    rec_P_good = child_good * (1 - p_node)
                    X = (base + P_bad * (rec_base / rec_P_good)) / P_good
                else:
                    X = base / P_good
            if X < best_cost:
                best_cost = X
                best_decision = (inspect, dismantle)
    return best_cost, best_decision


def solve_problem3_with_p(p):
    global L_final, s_f
    parts = {1: (p, 2, 1), 2: (p, 8, 1), 3: (p, 12, 2), 4: (p, 2, 1),
             5: (p, 8, 1), 6: (p, 12, 2), 7: (p, 8, 1), 8: (p, 12, 2)}
    semi = {1: (p, 8, 4, 6), 2: (p, 8, 4, 6), 3: (p, 8, 4, 6)}
    final = (p, 8, 6)
    semi_children = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8]}
    final_children = [1, 2, 3]
    L_final = 40
    s_f = 200

    part_costs = {}
    for pid in parts:
        best_c, best_d = float('inf'), None
        for insp in (0, 1):
            c, _ = part_supply(pid, parts[pid][0], parts[pid][1], parts[pid][2], insp)
            if c < best_c:
                best_c, best_d = c, insp
        part_costs[pid] = (best_c, best_d)
    semi_costs = {}
    for sid in semi:
        children = []
        for cid in semi_children[sid]:
            c, _ = part_costs[cid]
            pp, _, _ = parts[cid]
            g = 1.0 if part_costs[cid][1] else (1 - pp)
            children.append((c, g))
        p_node, ca, t_node, r_node = semi[sid]
        cost, decision = node_cost(children, p_node, ca, t_node, r_node, is_final=False)
        semi_costs[sid] = (cost, decision)
    children = []
    for sid in final_children:
        c, _ = semi_costs[sid]
        p_node, _, _, _ = semi[sid]
        sub_good = 1.0
        for cid in semi_children[sid]:
            pp, _, _ = parts[cid]
            g = 1.0 if part_costs[cid][1] else (1 - pp)
            sub_good *= g
        g_semi = sub_good * (1 - p_node)
        children.append((c, g_semi))
    p_node, ca, t_node = final
    cost, decision = node_cost(children, p_node, ca, t_node, None, is_final=True)
    return cost, decision


print("=" * 80)
print("2024国赛B题 问题4：抽样估计次品率下的稳健决策（重做问题3）")
print("=" * 80)
p_true3 = 0.10
x3 = round(n_sample * p_true3)
p_hat3 = x3 / n_sample
p_low3, p_high3 = wilson_ci(x3, n_sample)
print(f"真实次品率 p={p_true3:.0%}，抽 n={n_sample} 件，观测次品数 x={x3}，"
      f"点估计={p_hat3:.4f}，95%CI=[{p_low3:.4f},{p_high3:.4f}]")
for tag, pe in [("乐观(下界)", p_low3), ("点估计", p_hat3), ("悲观(上界)", p_high3)]:
    cost, decision = solve_problem3_with_p(pe)
    print(f"  {tag:10s} p={pe:.4f}: 总期望净成本={cost:.4f}  成品决策(检测={decision[0]},拆解={decision[1]})")
print()
print("结论：若三种次品率下最优决策一致，则该决策对抽样不确定性稳健；")
print("否则需结合风险偏好（悲观/乐观）选择方案。")
