import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: {
    extension: "src/extension.ts",
    debugAdapter: "src/debugAdapter.ts",
  },
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node20",
  outdir: "out",
  external: ["vscode"],
  sourcemap: false,
  minify: true,
  logLevel: "info",
};

if (watch) {
  const context = await esbuild.context(options);
  await context.watch();
} else {
  await esbuild.build(options);
}
