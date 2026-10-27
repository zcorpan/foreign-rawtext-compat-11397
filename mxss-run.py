import sys
sys.path.insert(0, "/tmp/foreign-rawtext-compat-11397")
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import ff_compare
for mode in range(4):
    o = Options(); o.binary_location = sys.argv[1]; o.add_argument("-headless")
    o.set_preference("dom.parser.foreign_rawtext.mode", mode)
    d = webdriver.Firefox(options=o, service=Service(ff_compare.GECKODRIVER))
    d.get("file://" + __import__("os").path.abspath("mxss-check.html") + "")
    print("== mode", mode); print(d.find_element("id", "out").text)
    d.quit()
