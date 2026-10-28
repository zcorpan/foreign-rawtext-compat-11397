import sys
sys.path.insert(0, ".")
import frparse
from xml.etree import ElementTree as ET

def kids(e):
    out = []
    if e.text: out.append(("#text", e.text))
    for k in e:
        out.append((k.tag.split("}")[1] if isinstance(k.tag, str) else "#comment", "".join(k.itertext()) if isinstance(k.tag, str) else k.text))
        if k.tail: out.append(("#text", k.tail))
    return out

cases = [
    "<svg><style>a &gt; b {}</style><rect/></svg>",
    "<svg><style><![CDATA[ .a > .b{fill:red} ]]></style><rect/></svg>",
    "<svg><style><![CDATA[a]]> b <![CDATA[c]]>]]></style></svg>",
    "<svg><script><![CDATA[ if (a && b) x[y[0]]>1; ]]></script></svg>",
    "<svg><script>x[y[0]]>1</script></svg>",
    "<svg><script><!--\nfoo()\n--></script></svg>",
    "<svg><style/><rect/></svg>",
    "<svg><style>.a{}</svg><p>after",
    "<svg><title><b>x</b> &amp; y</title></svg>",
    "<style><![CDATA[a]]></style>",
    "<svg><script><![CDATA[ s='</script>' ]]></script></svg>",
    "<svg><style><![CDATA</style></svg>",
    "<svg><script><!-- x --></script></svg>",
]
for c in cases:
    for new in ("old", "raw", "rcdata"):
        doc, info = frparse.parse(c, new)
        recs = [(r["name"], r.get("ns"), r["switched"], kids(r["etree"]) if r.get("etree") is not None else None) for r in info["elements"]]
        print(new, repr(c), recs, info["cdata_open"], info["cdata_close"], info["eof_state"])
for c in ["<svg><style><![CDATA[a &amp; b &copy=1]]> &amp; </style></svg>"]:
    for m in ("old", "raw", "rcdata"):
        doc, info = frparse.parse(c, m)
        print(m, [kids(r["etree"]) for r in info["elements"]])
for c in ["<svg><style>.a<!-- -->{<!-- -->fill:none<!-- -->}</style></svg>", "<svg><title>4.5<!-- --> <!-- -->out</title></svg>", "<svg><style>a<!-- </style><img src=x onerror=alert(1)> -->b</style></svg>", "<svg><style>a<!-- x"]:
    for m in ("old", "rcdata", "rcdata-dc"):
        doc, info = frparse.parse(c, m)
        print(m, [kids(r["etree"]) for r in info["elements"]], [e.tag.split('}')[-1] for e in doc.iter() if isinstance(e.tag, str)])
for c in ["<svg><style><!--/*--><![CDATA[/* ><!--*/\n.a{fill:red}\n/*]]>*/--></style></svg>"]:
    for m in ("old", "rcdata", "rcdata-dc"):
        doc, info = frparse.parse(c, m)
        print(m, [kids(r["etree"]) for r in info["elements"]])
for c in ["<svg><title>4.5<!-- --> <!-- -->out</title></svg>", "<svg><title>a<!-- </title><img src=x> -->b</title></svg>",
          "<svg><style><!--/*--><![CDATA[/* ><!--*/\n.a{}\n/*]]>*/--></style></svg>", "<svg><title><!---->x<!-->y<!--->z</title></svg>"]:
    for m in ("old", "rcdata-c"):
        doc, info = frparse.parse(c, m)
        print(m, [kids(r["etree"]) for r in info["elements"]], [e.tag.split('}')[-1] for e in doc.iter() if isinstance(e.tag, str)][3:])
