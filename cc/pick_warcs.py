"""Pick a seeded random set of WARC paths from a Common Crawl crawl's warc.paths.gz."""
import gzip, hashlib, sys

paths_file, seed, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
paths = [l.strip() for l in gzip.open(paths_file, "rt") if l.strip()]
paths.sort(key=lambda p: hashlib.sha256((seed + p).encode()).hexdigest())
for p in paths[:n]:
    print(p)
