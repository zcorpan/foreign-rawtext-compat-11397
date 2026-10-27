"""Check that each dom.parser.foreign_rawtext.mode value takes effect in the build."""
import sys, urllib.parse
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import ff_compare

HTML = "<svg><style>a &gt; b<!-- c -->{}</style><title>4.5<!-- --> x</title></svg>"
for mode in range(4):
    opts = Options()
    opts.binary_location = sys.argv[1]
    opts.add_argument("-headless")
    opts.set_preference("dom.parser.foreign_rawtext.mode", mode)
    d = webdriver.Firefox(options=opts, service=Service(ff_compare.GECKODRIVER))
    d.get("data:text/html," + urllib.parse.quote(HTML))
    print(mode, d.execute_script("return [...document.querySelectorAll('svg > *')].map(e => [e.localName, [...e.childNodes].map(n => n.nodeType == 8 ? '#c' : n.data)])"))
    d.quit()
