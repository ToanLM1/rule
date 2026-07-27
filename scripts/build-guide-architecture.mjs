import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repositoryRoot = fileURLToPath(new URL("../", import.meta.url));
const commandShell = process.env.ComSpec || "cmd.exe";
const npmRoot = execFileSync(commandShell, ["/d", "/s", "/c", "npm.cmd root --global"], {
  encoding: "utf8",
}).trim();
const kitRoot = join(npmRoot, "drawio-ai-kit");

const { Diagram } = await import(pathToFileURL(join(kitRoot, "src", "builder.mjs")).href);
const { box, frame, grid, phantom, renderTree } = await import(
  pathToFileURL(join(kitRoot, "src", "layout-engine.mjs")).href
);

const outputDirectory = join(repositoryRoot, "docs", "diagrams");
const outputPath = join(outputDirectory, "rule-platform-guide-architecture.drawio");
const svgOutputPath = join(
  repositoryRoot,
  "ui",
  "public",
  "guide",
  "slides",
  "rule-platform-architecture.svg",
);
mkdirSync(outputDirectory, { recursive: true });

const diagram = new Diagram("rule-platform-guide-architecture");

const palette = {
  canvas: "#F3F6FA",
  panel: "#FFFFFF",
  panelAlt: "#EDF2F8",
  border: "#A8B5C7",
  blue: "#4F86F7",
  blueSoft: "#DCE8FF",
  silver: "#253247",
  muted: "#708198",
  green: "#5CC79B",
  greenSoft: "#D8F3E7",
  amber: "#E4AA58",
  amberSoft: "#FAECD8",
};

const card = (id, label, options = {}) =>
  box(id, label, {
    w: 178,
    h: 70,
    fill: palette.panelAlt,
    stroke: palette.border,
    fontColor: palette.silver,
    rounded: true,
    ...options,
  });

const stage = (id, label, children, options = {}) =>
  frame(
    id,
    label,
    {
      dir: "col",
      gap: 16,
      pad: 22,
      fill: palette.panel,
      stroke: palette.border,
      fontColor: palette.silver,
      rounded: true,
      ...options,
    },
    children,
  );

const inputs = stage(
  "inputs",
  "Bootstrap inputs",
  [
    grid("input_grid", null, "", { cols: 2, gap: 14, stroke: "none", fill: palette.panel }, [
      card("java_repo", "Small public\nJava repository"),
      card("postgres_table", "Selected\nPostgreSQL table"),
    ]),
  ],
  { stroke: palette.muted },
);

const evidence = stage(
  "evidence",
  "Evidence acquisition",
  [
    card("bounded_tools", "Pinned source +\nbounded evidence tools", {
      stroke: palette.blue,
    }),
    card("candidate_llm", "Candidate-only LLM\nschema validated", {
      fill: "#E8F0FF",
      stroke: palette.blue,
    }),
    card("evidence_bundle", "EvidenceBundle +\ncandidate package", {
      fill: palette.blueSoft,
      stroke: palette.blue,
      bold: true,
    }),
  ],
  { stroke: palette.blue },
);

const governance = stage(
  "governance",
  "Business-owned governance hub",
  [
    card("decision_package", "Canonical Decision\nPackage", {
      fill: palette.blueSoft,
      stroke: palette.blue,
      bold: true,
    }),
    card("studio", "Canonical Studio\nbusiness authoring", {
      stroke: palette.blue,
    }),
    card("maker_checker", "Maker submits\nChecker approves", {
      fill: palette.amberSoft,
      stroke: palette.amber,
      bold: true,
    }),
  ],
  { stroke: palette.amber },
);

const proof = stage(
  "proof",
  "Deterministic proof",
  [
    card("compiler", "Validated package\ncompiler"),
    card("rule_ir", "Executable\nRule IR", {
      fill: palette.blueSoft,
      stroke: palette.blue,
      bold: true,
    }),
    card("golden_tests", "Approved golden suite\n+ lookup snapshots", {
      fill: palette.greenSoft,
      stroke: palette.green,
      bold: true,
    }),
  ],
  { stroke: palette.green },
);

const delivery = stage(
  "delivery",
  "Delivery boundary",
  [
    card("generated_java", "Mode B - active MVP\nDeterministic Java + JUnit", {
      stroke: palette.green,
    }),
    card("target_tests", "Compile + generated\n+ target tests", {
      fill: palette.greenSoft,
      stroke: palette.green,
    }),
    card("reviewable_pr", "Pushed branch +\nreviewable pull request", {
      fill: palette.greenSoft,
      stroke: palette.green,
      bold: true,
    }),
    card("zen_runtime", "Mode A - retained, deferred\nZen managed runtime", {
      fill: palette.amberSoft,
      stroke: palette.amber,
    }),
    card("drift_cycle", "Source drift\nre-enters evidence review", {
      fill: "#F1ECFF",
      stroke: "#8B72C7",
    }),
  ],
  { stroke: palette.green },
);

const root = frame(
  "root",
  "Rule Platform - governed change architecture",
  {
    dir: "row",
    gap: 24,
    align: "top",
    pad: 30,
    fill: palette.canvas,
    stroke: palette.border,
    fontColor: palette.silver,
    rounded: true,
  },
  [inputs, evidence, governance, proof, delivery],
);

renderTree(diagram, root, [40, 70]);

diagram.link("java_repo", "bounded_tools", "", { flow: true });
diagram.link("postgres_table", "bounded_tools", "", { flow: true });
diagram.link("bounded_tools", "candidate_llm", "", { flow: true });
diagram.link("candidate_llm", "evidence_bundle", "", { dash: true });
diagram.link("evidence_bundle", "decision_package", "", { flow: true });
diagram.link("decision_package", "studio", "", { flow: true });
diagram.link("studio", "maker_checker", "", { flow: true });
diagram.link("maker_checker", "compiler", "", { flow: true });
diagram.link("compiler", "rule_ir", "", { flow: true });
diagram.link("rule_ir", "golden_tests", "", { flow: true });
diagram.link("golden_tests", "generated_java", "", { flow: true });
diagram.link("generated_java", "target_tests", "", { flow: true });
diagram.link("target_tests", "reviewable_pr", "", { flow: true });
diagram.link("rule_ir", "zen_runtime", "", { dash: true });
diagram.link("reviewable_pr", "drift_cycle", "", { dash: true });

const validation = diagram.validate();
if (!validation.ok) {
  throw new Error(JSON.stringify(validation.errors, null, 2));
}

writeFileSync(outputPath, diagram.mxfile("Rule Platform Guide Architecture"));

if (process.env.DRAWIO_CLI) {
  execFileSync(
    process.env.DRAWIO_CLI,
    ["--export", "--format", "svg", "--crop", "--output", svgOutputPath, outputPath],
    { stdio: "inherit" },
  );

  const svg = readFileSync(svgOutputPath, "utf8");
  const reducedMotionRule =
    '@media (prefers-reduced-motion: reduce){[style*="animation:"]{animation:none!important;stroke-dashoffset:0!important;}}';
  writeFileSync(
    svgOutputPath,
    svg.replace("</style></defs>", `${reducedMotionRule}</style></defs>`),
  );
  console.log(svgOutputPath);
}

console.log(outputPath);
console.log(
  JSON.stringify({
    warnings: validation.warnings,
    advice: validation.audit.advice,
  }),
);
