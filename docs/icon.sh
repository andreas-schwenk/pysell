#!/bin/bash
convert -resize 16x16 logo.svg logo.ico
base64 -i logo.ico
