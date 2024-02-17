import esbuild from "esbuild";

// build minified javascript file dist/sell.min.js
esbuild.buildSync({
  platform: "browser",
  globalName: "sell",
  minify: true,
  target: "",
  entryPoints: ["src/index.js"],
  bundle: true,
  outfile: "dist/sell.min.js",
});
