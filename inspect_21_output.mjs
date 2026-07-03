import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "D:/DDocuments/guangdong/field_table.xlsx";
const outputPath = "D:/DDocuments/guangdong/inspect_21_output.txt";

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheetName = "2.1输出";

const summary = await workbook.inspect({
  kind: "sheet,table,region,computedStyle",
  sheetId: sheetName,
  range: "A1:F20",
  maxChars: 12000,
  tableMaxRows: 20,
  tableMaxCols: 8,
});

const preview = await workbook.render({
  sheetName,
  autoCrop: "all",
  scale: 1,
  format: "png",
});

await fs.writeFile(outputPath, summary.ndjson, "utf8");
await fs.writeFile(
  "D:/DDocuments/guangdong/inspect_21_output.png",
  new Uint8Array(await preview.arrayBuffer()),
);
