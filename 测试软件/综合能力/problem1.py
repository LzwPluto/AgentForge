import math

def binom_pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))

def binom_cdf(k, n, p):
    return sum(binom_pmf(i, n, p) for i in range(0, k + 1))

def find_min_n_case1(p0=0.10, confidence=0.95):
    """
    情形(1)：95%信度认定次品率超过标称值则拒收。
    抽样方案(n,k)：若样本次品数 X > k 则拒收。
    需控制误拒(在p=p0时错误拒收) <= 5%，即 P(X<=k|p0) >= 95%。
    对每个 n 取最小 k 使 P(X<=k|p0)>=0.95，且 k<n（保证可拒收）。
    取最小 n。
    """
    n = 1
    while True:
        k = 0
        while True:
            prob = binom_cdf(k, n, p0)
            if prob >= confidence:
                break
            k += 1
        prob_accept = binom_cdf(k, n, p0)   # P(X<=k)
        prob_reject = 1 - prob_accept        # 误拒概率
        if k < n:
            return n, k, prob_accept, prob_reject
        n += 1

def find_min_n_case2(p0=0.10, confidence=0.90):
    """
    情形(2)：90%信度认定次品率不超过标称值则接收。
    抽样方案(n,k)：若样本次品数 X <= k 则接收（k 尽量大）。
    需控制误收(在p=p0时错误接收) <= 10%，即 P(X<=k|p0) <= 10%。
    对每个 n 取最大 k 使 P(X<=k|p0)<=0.10，且 k>=0（保证可接收）。
    取最小 n。
    """
    n = 1
    while True:
        k = -1
        while k + 1 <= n:
            if binom_cdf(k + 1, n, p0) <= (1 - confidence):
                k += 1
            else:
                break
        if k >= 0:
            prob_accept = binom_cdf(k, n, p0)  # P(X<=k)=误收概率
            return n, k, prob_accept, 1 - prob_accept
        n += 1

print("=" * 60)
print("情形(1)：95%信度认定次品率超过标称值则拒收")
print("=" * 60)
n1, k1, pa1, pr1 = find_min_n_case1()
print(f"最小样本量 n = {n1}")
print(f"临界值 k = {k1}（样本次品数 > {k1} 则拒收，即 X >= {k1+1} 拒收）")
print(f"p=10%时 P(X<={k1}) = {pa1:.6f}，误拒概率 = {pr1:.6f}")
print(f"临界次品率 (k+1)/n = {k1+1}/{n1} = {(k1+1)/n1:.4f}")
for p_test in [0.10, 0.12, 0.15, 0.20]:
    print(f"  若实际次品率 p={p_test:.0%}，拒收概率 = {1-binom_cdf(k1,n1,p_test):.4f}")

print()
print("=" * 60)
print("情形(2)：90%信度认定次品率不超过标称值则接收")
print("=" * 60)
n2, k2, pa2, pr2 = find_min_n_case2()
print(f"最小样本量 n = {n2}")
print(f"临界值 k = {k2}（样本次品数 <= {k2} 则接收）")
print(f"p=10%时 P(X<={k2}) = {pa2:.6f}，误收概率 = {pa2:.6f}")
print(f"临界次品率 k/n = {k2}/{n2} = {k2/n2:.4f}")
for p_test in [0.05, 0.08, 0.10]:
    print(f"  若实际次品率 p={p_test:.0%}，接收概率 = {binom_cdf(k2,n2,p_test):.4f}")
