import math

def pge(k, n, p):
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))

def ple(k, n, p):
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))

def pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))

p0 = 0.10
n = 22
print('n =', n)
print('P(X=0|22,0.1) =', pmf(0, n, p0), '=', round(pmf(0, n, p0), 4))
print('P(X<=0|22,0.1) =', ple(0, n, p0))
print('P(X>=6|22,0.1) =', pge(6, n, p0), '=', round(pge(6, n, p0), 4))
print('P(X<=5|22,0.1) =', ple(5, n, p0))
print('P(1<=X<=5|22,0.1) =', ple(5, n, p0) - ple(0, n, p0))

# verify no smaller n works for acceptance
print('\nCheck acceptance feasibility for n<22:')
for n in range(1, 22):
    ca = None
    for cc in range(n, -1, -1):
        if ple(cc, n, p0) <= 0.10:
            ca = cc
            break
    print('n =', n, ' c_accept =', ca, ' P(X<=0)=', round(pmf(0,n,p0),4))
