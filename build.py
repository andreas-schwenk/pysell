"""
This script is only intended for pySELL development. 
Users just use file 'sell.py'
"""

import subprocess

try:
    res = subprocess.run(["npm", "install"], cwd="web")
    res = subprocess.run(["node", "build.js"], cwd="web")
except Exception as e:
    print(e)
    print("pySELL dependencies: npm+nodejs")
    print("          https://www.npmjs.com, https://nodejs.org/")
    print("          https://nodejs.org/en/download/package-manager")
    print("[Debian]  sudo apt install nodejs npm")
    print("[macOS]   brew install node")
