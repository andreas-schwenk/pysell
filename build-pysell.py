#!/usr/bin/env python3

"""
pySELL - Python based Simple E-Learning Language for the simple creation of 
         interactive courses
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3

This script is only intended for pySELL development. 
Users just use file 'sell.py' (python sell.py QUESTION_FILE.txt)
"""


import subprocess

print("pySELL builder - 2024 by Andreas Schwenk")

if __name__ == "__main__":

    # build web
    try:
        # install web dependencies
        res = subprocess.run(["npm", "install"], cwd="web", check=False)
        # build web
        res = subprocess.run(["node", "build.js"], cwd="web", check=False)
    except Exception as e:
        print(e)
        print("pySELL dependencies: npm+nodejs")
        print("          https://www.npmjs.com, https://nodejs.org/")
        print("          https://nodejs.org/en/download/package-manager")
        print("[Debian]  sudo apt install nodejs npm")
        print("[macOS]   brew install node")

    # build html template and update sell.py
    with open("web/index.html", mode="r", encoding="utf-8") as f:
        index_html_lines = f.readlines()
    with open("web/dist/pysell.min.js", mode="r", encoding="utf-8") as f:
        js = f.read().strip()
    with open("sell.py", mode="r", encoding="utf-8") as f:
        sell_py_lines = f.readlines()

    # remove code between @begin(test) and @end(test)
    html: str = ""
    skip: bool = False
    for line in index_html_lines:
        if "@begin(test)" in line:
            skip = True
        elif "@end(test)" in line:
            skip = False
        elif skip is False:
            html += line

    # remove white spaces
    html = html.replace("  ", "").replace("\n", " ")

    # insert javascript code
    html = html.replace(
        "</body>",
        "<script>let debug = false; let quizSrc = {};"
        + js
        + "pysell.init(quizSrc,debug);</script></body>",
    )

    # update file "sell.py" between "# @begin(html" and "# @end(html)"
    py: str = ""
    skip: bool = False
    for line in sell_py_lines:
        if "@begin(html)" in line:
            skip = True
        elif "@end(html)" in line:
            skip = False
            # begin HTML
            py += "# @begin(html)\n"
            # insert HTML as byte-strings
            py += "HTML: str = b''\n"
            html_bytes = html.encode("utf-8")
            while len(html_bytes) > 0:
                py += "HTML += " + str(html_bytes[:60]) + "\n"
                html_bytes = html_bytes[60:]
            py += "HTML = HTML.decode('utf-8')\n"
            # end HTML
            py += "# @end(html)\n"
        elif skip is False:
            py += line

    # write new version of sell.py
    with open("sell.py", mode="w", encoding="utf-8") as f:
        f.write(py.strip() + "\n")

# compile example
res = subprocess.run(
    ["python3", "sell.py", "-J", "examples/ex1.txt"], cwd=".", check=False
)

# update example in docs/
res = subprocess.run(["cp", "examples/ex1.html", "docs/"], cwd=".", check=False)
