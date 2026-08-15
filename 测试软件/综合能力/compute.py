import math

def pge(k, n, p):
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))

def ple(k, n, p):
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(0, k + 1))

p0 = 0.10

print('=== Decision 1: reject 95% confidence ===')
for n in range(1, 200):
    c = None
    for cc in range(0, n + 1):
        if pge(cc, n, p0) <= 0.05:
            c = cc
            break
    if c is not None:
        print('n =', n, ' c_reject =', c, ' P(X>=c) =', round(pge(c, n, p0), 4), ' E[X] =', round(n * p0, 1))
        break

print()
print('=== Decision 2: accept 90% confidence ===')
for n in range(1, 100):
    c = None
    for cc in range(n, -1, -1):
        if ple(cc, n, p0) <= 0.10:
            c = cc
            break
    if c is not None:
        print('n =', n, ' c_accept =', c, ' P(X<=c) =', round(ple(c, n, p0), 4), ' E[X] =', round(n * p0, 1))
        break

print()
print('=== Full plan: single n where both feasible and c_accept < c_reject ===')
for n in range(1, 300):
    ca = None
    for cc in range(n, -1, -1):
        if ple(cc, n, p0) <= 0.10:
            ca = cc
            break
    cr = None
    for cc in range(0, n + 1):
        if pge(cc, n, p0) <= 0.05:
            cr = cc
            break
    if ca is not None and cr is not None and ca < cr:
        print('n =', n, ' c_accept =', ca, ' c_reject =', cr,
              ' P_accept=0.90 case P(X<=ca)=', round(ple(ca, n, p0), 4),
              ' P_reject=0.95 case P(X>=cr)=', round(pge(cr, n, p0), 4))
        break
