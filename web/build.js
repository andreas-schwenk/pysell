import esbuild from "esbuild";

// build minified javascript file dist/pysell.min.js
esbuild.buildSync({
  platform: "browser",
  globalName: "pysell",
  minify: true,
  target: "",
  entryPoints: ["src/index.js"],
  bundle: true,
  keepNames: true,
  outfile: "dist/pysell.min.js",
});
