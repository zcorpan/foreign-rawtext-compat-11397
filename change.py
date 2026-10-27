# The change under test. compare.py, recheck.py, and analyze.py import this; the rest is generic.
# Visits A and A2 use the "before" setup, B the "after" setup. Leave unused hooks as they are.

# Browser launch arguments, e.g. ['--disable-blink-features=Foo'] or ['--disable-features=Foo'].
BEFORE_ARGS = []
AFTER_ARGS = []

# Emulation, when no switch or build implements the change: a script injected before page scripts
# run (parse-time and API changes), and/or an async function expression run in B after load (DOM
# rewrites; compare.py waits again before measuring).
AFTER_INIT_JS = None
AFTER_LOAD_JS = None

# Injected into every visit before page scripts run, e.g. to record call stacks of an API.
INIT_JS = None

# Function expression returning change-specific measurements (element boxes, stacks recorded by
# INIT_JS, etc.); stored as 'extra' for the page and each frame.
EXTRA_MEASURE_JS = None

# Checked on sanity/<SANITY_PAGE> before the run: an expression that is true only when the change
# is in effect. compare.py stops if A is true or B is false.
SANITY_PAGE = None
SANITY_JS = None


def classify(r):
    """Change-specific auto-rating for a page analyze.py couldn't rate: (rating, reason) or None."""
    return None
