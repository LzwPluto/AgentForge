# -*- coding: utf-8 -*-
"""
2024国赛B题 问题2：两零配件生产决策优化
基于建模手 model_problem234.md 的期望成本模型，含拆解后二次检测。

核心量：
  配件i供给1件合格件成本：di=1 -> Pi=(ci+ti)/(1-pi)；di=0 -> Pi=ci
  gi = 1-pi 若 di=0；gi=1 若 di=1        (配件i合格的期望概率)
  P_good = g1*g2*(1-pf)                   (成品合格概率)
  P_bad  = 1-P_good

X  = 从全新配件出发交付1件合格成品到市场的期望净成本（含退回/报废/拆解再加工）
X_rec = 从回收配件出发交付1件的期望净成本

递推（解析闭合解，无需迭代）：
  base   = (P1+P2) + ca + tf*df
  L_m    = L 若 df==0（不合格流入市场被退回）; 0 若 df==1
  若 dr==0（报废，每次失败都从全新配件重来）:
      X = [base - P_good*s + P_bad*L_m] / P_good
  若 dr==1（拆解，回收配件再加工）:
      X_rec = [base_rec - P_good'*s + P_bad'*L_m] / P_good'
      X     = base - P_good*s + P_bad*L_m + P_bad*X_rec
  其中 base_rec, P_good' 由回收配件+二次检测决定。

枚举 (d1,d2,df,dr,d1',d2') 共 64 种，取 X 最小者为最优。
"""


def solve_case(p1, c1, t1, p2, c2, t2, pf, ca, tf, s, L, r, label):
    best_X = float('inf')
    best = None
    results = []

    for d1 in (0, 1):
        for d2 in (0, 1):
            for df in (0, 1):
                for dr in (0, 1):
                    for d1p in (0, 1):
                        for d2p in (0, 1):
                            # ---- 配件供给成本 ----
                            P1 = (c1 + t1) / (1 - p1) if d1 else c1
                            P2 = (c2 + t2) / (1 - p2) if d2 else c2
                            P_part = P1 + P2
                            # 配件合格概率
                            g1 = 1.0 if d1 else (1 - p1)
                            g2 = 1.0 if d2 else (1 - p2)
                            P_good = g1 * g2 * (1 - pf)
                            P_bad = 1 - P_good
                            base = P_part + ca + tf * df
                            L_m = L if df == 0 else 0.0

                            if dr == 0:
                                # 报废：失败即从全新件重来
                                X = (base - P_good * s + P_bad * L_m) / P_good
                                X_rec = None
                            else:
                                # 拆解：回收配件再加工
                                # 回收件 i 的次品概率 qi = 0 若 di=1; =pi 若 di=0
                                q1 = 0.0 if d1 else p1
                                q2 = 0.0 if d2 else p2
                                # 二次检测后回收件成本
                                cost_rec1 = q1 * (c1 + t1) / (1 - p1) if d1p else 0.0
                                cost_rec2 = q2 * (c2 + t2) / (1 - p2) if d2p else 0.0
                                base_rec = (cost_rec1 + cost_rec2) + ca + tf * df + r
                                # 回收件二次检测后合格概率
                                g1p = 1.0 if d1p else (1 - q1)
                                g2p = 1.0 if d2p else (1 - q2)
                                P_good_rec = g1p * g2p * (1 - pf)
                                P_bad_rec = 1 - P_good_rec
                                X_rec = (base_rec - P_good_rec * s + P_bad_rec * L_m) / P_good_rec
                                X = base - P_good * s + P_bad * L_m + P_bad * X_rec

                            results.append({
                                'd1': d1, 'd2': d2, 'df': df, 'dr': dr,
                                'd1p': d1p, 'd2p': d2p, 'X': X,
                                'P_good': P_good, 'P_bad': P_bad,
                            })
                            if X < best_X:
                                best_X = X
                                best = results[-1]

    print("=" * 78)
    print(f"情形 {label}  (p1={p1},p2={p2},pf={pf}, L={L}, r={r})")
    print("=" * 78)
    print(f"  最优期望净成本 X = {best_X:.4f} 元/件（负值表示盈利）")
    print(f"  最优决策：")
    print(f"    配件1检测 d1  = {best['d1']}")
    print(f"    配件2检测 d2  = {best['d2']}")
    print(f"    成品检测 df   = {best['df']}")
    print(f"    不合格品拆解 dr = {best['dr']}")
    print(f"    拆解后配件1二次检测 d1' = {best['d1p']}")
    print(f"    拆解后配件2二次检测 d2' = {best['d2p']}")
    print(f"  成品合格率 P_good = {best['P_good']:.4f}  不合格率 P_bad = {best['P_bad']:.4f}")
    print()
    # 打印次优方案供对比
    results.sort(key=lambda r: r['X'])
    print("  Top5 决策方案对比：")
    for r in results[:5]:
        print(f"    d1={r['d1']} d2={r['d2']} df={r['df']} dr={r['dr']} "
              f"d1'={r['d1p']} d2'={r['d2p']}  X={r['X']:.4f}  P_good={r['P_good']:.3f}")
    print()
    return best, best_X


# 表1 六种情形数据
scenarios = [
    dict(p1=0.10, c1=4, t1=2, p2=0.10, c2=18, t2=3, pf=0.10, ca=6, tf=3, s=56, L=6, r=5, label=1),
    dict(p1=0.20, c1=4, t1=2, p2=0.20, c2=18, t2=3, pf=0.20, ca=6, tf=3, s=56, L=6, r=5, label=2),
    dict(p1=0.10, c1=4, t1=2, p2=0.10, c2=18, t2=3, pf=0.10, ca=6, tf=3, s=56, L=30, r=5, label=3),
    dict(p1=0.20, c1=4, t1=1, p2=0.20, c2=18, t2=1, pf=0.20, ca=6, tf=2, s=56, L=30, r=5, label=4),
    dict(p1=0.10, c1=4, t1=8, p2=0.20, c2=18, t2=1, pf=0.10, ca=6, tf=2, s=56, L=10, r=5, label=5),
    dict(p1=0.05, c1=4, t1=2, p2=0.05, c2=18, t2=3, pf=0.05, ca=6, tf=3, s=56, L=10, r=40, label=6),
]

if __name__ == "__main__":
    for sc in scenarios:
        label = sc.pop('label')
        solve_case(**sc, label=label)
