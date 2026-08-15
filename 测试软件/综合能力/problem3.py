# -*- coding: utf-8 -*-
"""
2024国赛B题 问题3：多工序多配件生产决策优化（动态规划）
结构（建模手确认）：
  成品 <- {半成品1, 半成品2, 半成品3}
  半成品1 <- {配件1, 配件2, 配件3}
  半成品2 <- {配件4, 配件5, 配件6}
  半成品3 <- {配件7, 配件8}

表2数据：
  配件: 1(10%,2,1) 2(10%,8,1) 3(10%,12,2) 4(10%,2,1)
        5(10%,8,1) 6(10%,12,2) 7(10%,8,1) 8(10%,12,2)
  半成品1,2,3: 次品率10%, 装配成本8, 检测成本4, 拆解费6
  成品: 次品率10%, 装配成本8, 检测成本6
  市场售价200, 调换损失40
"""

parts = {
    1: (0.10, 2, 1), 2: (0.10, 8, 1), 3: (0.10, 12, 2),
    4: (0.10, 2, 1), 5: (0.10, 8, 1), 6: (0.10, 12, 2),
    7: (0.10, 8, 1), 8: (0.10, 12, 2),
}
semi = {1: (0.10, 8, 4, 6), 2: (0.10, 8, 4, 6), 3: (0.10, 8, 4, 6)}
final = (0.10, 8, 6)

semi_children = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8]}
final_children = [1, 2, 3]

s = 200
L = 40


def part_cost(part_id, inspect):
    p, c, t = parts[part_id]
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
                L_m = L if not inspect else 0
                if dismantle:
                    rec_child_cost = child_cost
                    rec_base = rec_child_cost + ca + (t_node if inspect else 0)
                    rec_P_good = child_good * (1 - p_node)
                    rec_P_bad = 1 - rec_P_good
                    X_rec = (rec_base + r_node - rec_P_good * s + rec_P_bad * L_m) / rec_P_good
                    X = base - P_good * s + P_bad * L_m + P_bad * X_rec
                else:
                    X = (base - P_good * s + P_bad * L_m) / P_good
            else:
                if dismantle:
                    rec_child_cost = child_cost
                    rec_base = rec_child_cost + ca + (t_node if inspect else 0) + r_node
                    rec_P_good = child_good * (1 - p_node)
                    rec_P_bad = 1 - rec_P_good
                    X = (base + P_bad * (rec_base / rec_P_good)) / P_good
                else:
                    X = base / P_good

            if X < best_cost:
                best_cost = X
                best_decision = (inspect, dismantle)
    return best_cost, best_decision


def solve_problem3():
    print("=" * 78)
    print("2024国赛B题 问题3：多工序多配件生产决策优化（动态规划）")
    print("=" * 78)

    part_costs = {}
    print("\n--- 配件层 ---")
    for pid in parts:
        best_c = float('inf')
        best_d = None
        for insp in (0, 1):
            c, _ = part_cost(pid, insp)
            if c < best_c:
                best_c = c
                best_d = insp
        part_costs[pid] = (best_c, best_d)
        print(f"  配件{pid}: 最优检测={best_d}, 供给成本={best_c:.4f}")

    print("\n--- 半成品层 ---")
    semi_costs = {}
    for sid in semi:
        children = []
        for cid in semi_children[sid]:
            c, _ = part_costs[cid]
            p, _, _ = parts[cid]
            g = 1.0 if part_costs[cid][1] else (1 - p)
            children.append((c, g))
        p_node, ca, t_node, r_node = semi[sid]
        cost, decision = node_cost(children, p_node, ca, t_node, r_node, is_final=False)
        semi_costs[sid] = (cost, decision)
        print(f"  半成品{sid}: 最优(检测={decision[0]},拆解={decision[1]}), 成本={cost:.4f}")

    print("\n--- 成品层 ---")
    children = []
    for sid in final_children:
        c, _ = semi_costs[sid]
        p_node, _, _, _ = semi[sid]
        sub_good = 1.0
        for cid in semi_children[sid]:
            p, _, _ = parts[cid]
            g = 1.0 if part_costs[cid][1] else (1 - p)
            sub_good *= g
        g_semi = sub_good * (1 - p_node)
        children.append((c, g_semi))

    p_node, ca, t_node = final
    cost, decision = node_cost(children, p_node, ca, t_node, None, is_final=True)
    print(f"  成品: 最优(检测={decision[0]},拆解={decision[1]}), 期望净成本={cost:.4f} 元/件")

    print("\n" + "-" * 78)
    print("【问题3 最优决策方案汇总】")
    print("-" * 78)
    for pid in parts:
        print(f"  配件{pid}: {'检测' if part_costs[pid][1] else '不检测'}")
    for sid in semi:
        d = semi_costs[sid][1]
        print(f"  半成品{sid}: {'检测' if d[0] else '不检测'}, 不合格品{'拆解' if d[1] else '报废'}")
    print(f"  成品: {'检测' if decision[0] else '不检测'}, 不合格品{'拆解' if decision[1] else '报废'}")
    print(f"  总期望净成本: {cost:.4f} 元/件（负值表示盈利）")
    print(f"  市场售价: {s} 元/件, 调换损失: {L} 元/件")


if __name__ == "__main__":
    solve_problem3()
