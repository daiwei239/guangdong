import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "D:/DDocuments/guangdong/field_table.xlsx";
const outputDir = "D:/DDocuments/guangdong/outputs/clusterdata-2026-compare";
const outputPath = `${outputDir}/field_table_clusterdata_2026_compared.xlsx`;
const previewPath = `${outputDir}/field_table_clusterdata_2026_compared.png`;

const mappings = [
  ["直接映射", "cluster_id", "2026版 server_hourly / network_hourly 直接提供集群编号。"],
  ["缺失需自建", "-", "2026版未公开集群类型，如 AI、HPC、Hybrid。"],
  ["缺失需自建", "-", "2026版未公开区域/机房位置。"],
  ["直接映射", "server_id", "可直接作为节点编号。"],
  ["缺失需自建", "-", "2026版未公开 control、compute、storage 等节点角色。"],
  ["可聚合/推导", "pod state_public, ready_status, schedule_status", "可结合节点上的 pod 运行状态近似判断节点忙闲，但没有官方 node_status 字段。"],
  ["缺失需自建", "-", "2026版未公开 CPU 架构。"],
  ["缺失需自建", "-", "2026版未公开 CPU 型号。"],
  ["直接映射", "cpu_capacity_cores / server_cpu_capacity_cores", "直接给出 CPU 核心容量。"],
  ["缺失需自建", "-", "2026版没有当前可用核数字段，只有容量和请求/利用率相关信息。"],
  ["缺失需自建", "-", "2026版未公开 CPU 主频。"],
  ["可聚合/推导", "avg_cpu_request_util", "只有 CPU 请求利用相关指标，不是节点原生 CPU 使用率。"],
  ["缺失需自建", "-", "2026版未公开 NUMA 拓扑。"],
  ["可聚合/推导", "gpu_count / gpu_spec_public", "2026版默认是 GPU 集群，可由 GPU 字段推知加速器类型，但没有单独 accelerator_type 枚举。"],
  ["缺失需自建", "-", "2026版未公开 GPU 厂商字段。"],
  ["直接映射", "gpu_spec_public", "可作为公开后的 GPU 型号/规格。"],
  ["直接映射", "gpu_count / server_gpu_count", "直接给出 GPU 数量。"],
  ["缺失需自建", "-", "2026版没有当前可用 GPU 卡数量。"],
  ["缺失需自建", "-", "2026版未公开 GPU/NPU 切片总数。"],
  ["缺失需自建", "-", "2026版未公开 GPU/NPU 可用切片数。"],
  ["可聚合/推导", "gpu_spec_public", "规格字段可能间接反映显存档位，但没有标准显存总量字段。"],
  ["直接映射", "avg_gpu_sm_util", "可直接作为 GPU 利用率指标。"],
  ["缺失需自建", "-", "2026版未公开 GPU 温度。"],
  ["缺失需自建", "-", "2026版未公开节点总内存容量。"],
  ["缺失需自建", "-", "2026版未公开当前可用内存容量。"],
  ["缺失需自建", "-", "2026版未公开内存带宽。"],
  ["缺失需自建", "-", "2026版未公开本地存储总量。"],
  ["缺失需自建", "-", "2026版未公开本地可用存储。"],
  ["缺失需自建", "-", "2026版未公开共享存储可访问性。"],
  ["缺失需自建", "-", "2026版未公开存储读带宽。"],
  ["缺失需自建", "-", "2026版未公开存储写带宽。"],
  ["缺失需自建", "-", "2026版没有节点网络带宽上限，只公开实际收发流量。"],
  ["缺失需自建", "-", "2026版未公开网络时延。"],
  ["缺失需自建", "-", "2026版未公开丢包率。"],
  ["缺失需自建", "-", "2026版未公开 Ethernet、RoCE、IB 等互联类型。"],
  ["可聚合/推导", "asw_id", "只能映射到更粗粒度的交换机/拓扑域，不是精确 rack_id。"],
  ["缺失需自建", "-", "2026版未公开节点邻接关系。"],
  ["缺失需自建", "-", "2026版未公开节点间链路代价矩阵。"],
  ["缺失需自建", "-", "2026版未公开操作系统版本。"],
  ["缺失需自建", "-", "2026版未公开驱动版本。"],
  ["缺失需自建", "-", "2026版未公开 Docker、K8s、Slurm 等运行时栈。"],
  ["缺失需自建", "-", "2026版未公开 AI 框架列表。"],
  ["缺失需自建", "-", "2026版未公开 HPC 库环境。"],
  ["缺失需自建", "-", "2026版未公开算子库。"],
  ["可聚合/推导", "schedule_delay_sec, ready_delay_sec", "没有标准 queue_length，但可用调度/就绪延迟侧面表征排队压力。"],
  ["可聚合/推导", "schedule_delay_sec, ready_delay_sec", "可用延迟指标近似等待时间。"],
  ["缺失需自建", "-", "2026版未公开已预留资源明细。"],
  ["可聚合/推导", "pod_id / workload_id with state_public", "可按节点或集群聚合 Running 状态 pod 数量近似得到运行任务数。"],
  ["缺失需自建", "-", "2026版未公开 1 分钟系统负载 load_1min。"],
  ["缺失需自建", "-", "2026版未公开资源碎片化评分。"],
  ["可聚合/推导", "ready_status, schedule_status, avg_gpu_sm_util, delay metrics", "可由多项指标构造资源可用性评分，但数据集不直接提供。"],
  ["缺失需自建", "-", "2026版未公开当前功率。"],
  ["缺失需自建", "-", "2026版未公开能效评分。"],
  ["缺失需自建", "-", "2026版未公开近期失败率。"],
  ["缺失需自建", "-", "2026版未公开维护状态。"],
];

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheet = workbook.worksheets.getItem("2.1输出");

sheet.getRange("G1:I1").merge();
sheet.getRange("G1").values = [[
  "2026版对照：以 alibaba/clusterdata 的 cluster-trace-gpu-v2026 为准，标注每个 2.1 输出字段是否可直接映射、可推导或缺失。",
]];
sheet.getRange("G2:I2").values = [[
  "2026版映射状态",
  "clusterdata 2026 对应字段",
  "说明",
]];

sheet.getRange("G3:I57").values = mappings;

sheet.getRange("D2:F2").copyTo(sheet.getRange("G2:I2"), "all");
sheet.getRange("D3:F57").copyTo(sheet.getRange("G3:I57"), "all");

sheet.getRange("G1:I1").format = {
  fill: "#FFF7E6",
  font: { bold: true, color: "#7A3E00" },
  wrapText: true,
  horizontalAlignment: "left",
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#E6A23C" },
};
sheet.getRange("G2:I2").format = {
  fill: "#FAECD8",
  font: { bold: true, color: "#5A3B00" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D8C6A5" },
};
sheet.getRange("G3:G57").format.horizontalAlignment = "center";
sheet.getRange("G3:I57").format.verticalAlignment = "center";
sheet.getRange("H3:I57").format.wrapText = true;

sheet.getRange("G3:G57").conditionalFormats.add("containsText", {
  text: "直接映射",
  format: {
    fill: "#E8F5E9",
    font: { color: "#1B5E20", bold: true },
  },
});
sheet.getRange("G3:G57").conditionalFormats.add("containsText", {
  text: "可聚合/推导",
  format: {
    fill: "#FFF8E1",
    font: { color: "#8D6E00", bold: true },
  },
});
sheet.getRange("G3:G57").conditionalFormats.add("containsText", {
  text: "缺失需自建",
  format: {
    fill: "#FDECEC",
    font: { color: "#B42318", bold: true },
  },
});

sheet.getRange("G:I").format.columnWidth = 26;
sheet.getRange("H:H").format.columnWidth = 34;
sheet.getRange("I:I").format.columnWidth = 48;
sheet.getRange("1:2").format.rowHeight = 28;
sheet.getRange("1:1").format.rowHeight = 48;
sheet.freezePanes.freezeRows(2);
sheet.showGridLines = false;

await fs.mkdir(outputDir, { recursive: true });

const check = await workbook.inspect({
  kind: "table",
  sheetId: "2.1输出",
  range: "G1:I10",
  include: "values",
  tableMaxRows: 10,
  tableMaxCols: 3,
  maxChars: 4000,
});
await fs.writeFile(`${outputDir}/verify_21_output.txt`, check.ndjson, "utf8");

const preview = await workbook.render({
  sheetName: "2.1输出",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
