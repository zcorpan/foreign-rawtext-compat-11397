"""Clopper-Pearson 95% intervals and extrapolations for the live HTTP Archive samples."""
from math import comb

def cdf(k, n, p):
    return sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k + 1))

def cp(k, n, a=0.05):
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, n, p) < a / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, n, p) > a / 2)
    return lower, upper

rows = [
    ("rcdata (mode 2): visibly broken", 1, 100, 1444),
    ("rcdata-dc (mode 3): visibly broken", 0, 100, 1444),
    ("modes 2 and 3: React hydration errors", 4, 100, 1444),
    ("raw (mode 1), Wix: icons visibly recolored after load", 5, 100, 225901),
    ("raw (mode 1), Wix: style text still escaped after load", 17, 100, 225901),
]
for name, k, n, N in rows:
    lo, hi = cp(k, n)
    print(f"{name}: {k}/{n} -> ~{round(k / n * N)} of {N} pages (95% CI {round(lo * N)}-{round(hi * N)})")
