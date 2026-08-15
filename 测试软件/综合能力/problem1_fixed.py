# -*- coding: utf-8 -*-
"""
2024国赛B题 问题1 修正版
正确理解：
情形(1)：在95%信度下认定次品率超过标称值则拒收
  -> 当实际次品率 p = 10% 时，拒收概率 >= 95%
  -> 即 P(X > c | p=0.10) >= 0.95，等价于 P(X <= c | p=0.10) <= 0.05
  -> 找最小 n 和临界值 c，使得上述成立

情形(2)：在90%信度下认定次品率不超过标称值则接收
  -> 当实际次品率 p = 10% 时，接收概率 >= 90%
  -> 即 P(X <= c | p=0.10) >= 0.90
  -> 找最小 n 和临界值 c，使得上述成立
"""

from math import comb


def binom_pmf(k, n, p):
    """二项分布概率质量函数 P(X=k)"""
    return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_cdf(k, n, p):
    """二项分布累积分布函数 P(X<=k)"""
    return sum(binom_pmf(i, n, p) for i in range(0, k + 1))


def case1(p0=0.10, confidence=0.95):
    """
    情形(1)：95%信度认定次品率超过标称值则拒收
    要求：P(X <= c | p=p0) <= 1 - confidence = 0.05
    找最小 n 和对应的 c
    """
    for n in range(1, 500):
        c = -1
        while c + 1 <= n and binom_cdf(c + 1, n, p0) <= (1 - confidence) + 1e-12:
            c += 1
        if c >= 0:
            prob_reject = 1 - binom_cdf(c, n, p0)
            return n, c, prob_reject
    return None


def case2(p0=0.10, confidence=0.90):
    """
    情形(2)：90%信度认定次品率不超过标称值则接收
    要求：P(X <= c | p=p0) >= confidence = 0.90
    找最小 n 和对应的 c
    """
    for n in range(1, 500):
        c = 0
        while c <= n and binom_cdf(c, n, p0) < confidence - 1e-12:
            c += 1
        if c <= n:
            prob_accept = binom_cdf(c, n, p0)
            return n, c, prob_accept
    return None


def main():
    print("=" * 70)
    print("2024国赛B题 问题1 修正精确计算")
    print("=" * 70)

    p0 = 0.10
    print("\n【情形(1)】在95%信度下认定次品率超过标称值则拒收")
    print(f"  设定：当实际次品率 p={p0:.0%} 时，拒收概率应 >= 95%")
    print(f"  即 P(X>c | p=0.10) >= 0.95，等价于 P(X<=c | p=0.10) <= 0.05")
    r1 = case1()
    if r1:
        n1, c1, pr1 = r1
        print(f"  [结果] 最小样本量 n = {n1}")
        print(f"  [结果] 临界值 c = {c1}（样本中次品数 > {c1} 则拒收）")
        print(f"  [验证] P(X<={c1} | p=0.10) = {binom_cdf(c1, n1, p0):.8f}")
        print(f"  [验证] 拒收概率 P(X>{c1} | p=0.10) = {pr1:.8f} >= 0.95  OK")
        print(f"  临界次品率 c/n = {c1}/{n1} = {c1/n1:.4f}")
        print("  --- 不同实际次品率下的拒收概率 ---")
        for p in [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30]:
            print(f"    p={p:.0%}: 拒收概率 = {1 - binom_cdf(c1, n1, p):.4f}")
    else:
        print("  未找到解！")

    print("\n【情形(2)】在90%信度下认定次品率不超过标称值则接收")
    print(f"  设定：当实际次品率 p={p0:.0%} 时，接收概率应 >= 90%")
    print(f"  即 P(X<=c | p=0.10) >= 0.90")
    r2 = case2()
    if r2:
        n2, c2, pa2 = r2
        print(f"  [结果] 最小样本量 n = {n2}")
        print(f"  [结果] 临界值 c = {c2}（样本中次品数 <= {c2} 则接收）")
        print(f"  [验证] P(X<={c2} | p=0.10) = {pa2:.8f} >= 0.90  OK")
        print(f"  临界次品率 c/n = {c2}/{n2} = {c2/n2:.4f}")
        print("  --- 不同实际次品率下的接收概率 ---")
        for p in [0.02, 0.05, 0.08, 0.10, 0.12, 0.15]:
            print(f"    p={p:.0%}: 接收概率 = {binom_cdf(c2, n2, p):.4f}")
    else:
        print("  未找到解！")

    # 搜索过程关键信息
    print("\n" + "=" * 70)
    print("搜索过程关键方案")
    print("=" * 70)
    print("\n--- 情形(1) 满足 P(X<=c)<=0.05 的 n 递增情况 ---")
    for n in range(1, 40):
        c = -1
        while c + 1 <= n and binom_cdf(c + 1, n, p0) <= 0.05 + 1e-12:
            c += 1
        if c >= 0:
            print(f"  n={n:3d}, c={c:2d}, P(X<={c})={binom_cdf(c,n,p0):.6f}, 拒收率={1-binom_cdf(c,n,p0):.6f}")

    print("\n--- 情形(2) 满足 P(X<=c)>=0.90 的 n 递增情况 ---")
    for n in range(1, 40):
        c = 0
        while c <= n and binom_cdf(c, n, p0) < 0.90 - 1e-12:
            c += 1
        if c <= n:
            print(f"  n={n:3d}, c={c:2d}, P(X<={c})={binom_cdf(c,n,p0):.6f}, 接收率={binom_cdf(c,n,p0):.6f}")


if __name__ == "__main__":
    main()
