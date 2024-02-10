import fs from "fs";
import esbuild from "esbuild";

// build javascript
esbuild.buildSync({
  platform: "browser",
  globalName: "sell",
  minify: true,
  target: "",
  entryPoints: ["src/index.js"],
  bundle: true,
  outfile: "dist/sell.min.js",
});

// build html template and update sell.py
let lines = fs.readFileSync("index.html", "utf-8").split("\n");
let js = fs.readFileSync("dist/sell.min.js", "utf-8").trim();
//   remove code between @begin(test) and @end(test)
let html = "";
let skip = false;
for (let line of lines) {
  if (line.includes("@begin(test)")) skip = true;
  else if (line.includes("@end(test)")) skip = false;
  else if (skip == false) html += line + "\n";
}
//   remove white spaces
html = html.replaceAll("  ", "").replaceAll("\n", "");
//   insert javascript code
html = html.replace(
  "</body>",
  "<script>let quizSrc = {};" + js + "sell.init(quizSrc);</script>"
);
//   update file "sell.py" between "# @begin(html" and "# @end(html)"
lines = fs.readFileSync("sell.py", "utf-8").split("\n");
let py = "";
skip = false;
for (let line of lines) {
  if (line.includes("@begin(html)")) skip = true;
  else if (line.includes("@end(html)")) {
    skip = false;
    py += "# @begin(html)\n";
    py += 'html = """' + html + '\n"""\n';
    py += "# @end(html)\n";
  } else if (skip == false) py += line + "\n";
}
//   write new version of sell.py
fs.writeFileSync("sell.py", py);
