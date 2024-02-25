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
        res = subprocess.run(["npm", "install"], cwd="web")
        # build web
        res = subprocess.run(["node", "build.js"], cwd="web")
    except Exception as e:
        print(e)
        print("pySELL dependencies: npm+nodejs")
        print("          https://www.npmjs.com, https://nodejs.org/")
        print("          https://nodejs.org/en/download/package-manager")
        print("[Debian]  sudo apt install nodejs npm")
        print("[macOS]   brew install node")
    # build html template and update sell.py
    f = open("web/index.html")
    index_html_lines = f.readlines()
    f.close()
    f = open("web/dist/sell.min.js")
    js = f.read().strip()
    f.close()
    f = open("sell.py")
    sell_py_lines = f.readlines()
    f.close()
    # remove code between @begin(test) and @end(test)
    html = ""
    skip = False
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
        + "sell.init(quizSrc,debug);</script></body>",
    )
    # update file "sell.py" between "# @begin(html" and "# @end(html)"
    py = ""
    skip = False
    for line in sell_py_lines:
        if "@begin(html)" in line:
            skip = True
        elif "@end(html)" in line:
            skip = False
            # begin HTML
            py += "# @begin(html)\n"
            # insert HTML as byte-strings
            py += "html = b''\n"
            html_bytes = html.encode("utf-8")
            while len(html_bytes) > 0:
                py += "html += " + str(html_bytes[:60]) + "\n"
                html_bytes = html_bytes[60:]
            py += "html = html.decode('utf-8')\n"
            # end HTML
            py += "# @end(html)\n"
        elif skip is False:
            py += line
    # write new version of sell.py
    f = open("sell.py", "w")
    f.write(py.strip() + "\n")

# compile example
res = subprocess.run(["python3", "sell.py", "-J", "examples/ex1.txt"], cwd=".")

# update example in docs/
res = subprocess.run(["cp", "examples/ex1.html", "docs/"], cwd=".")
