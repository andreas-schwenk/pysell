import esbuild from "esbuild";

esbuild.buildSync({
  platform: "browser",
  globalName: "sell",
  minify: true,
  target: "",
  entryPoints: ["src/index.js"],
  bundle: true,
  outfile: "dist/sell.min.js",
});

// TODO: build "compressed" index.html and put it into sell.py
