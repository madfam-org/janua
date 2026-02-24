import Table from "cli-table3";
import yaml from "js-yaml";

export type OutputFormat = "table" | "json" | "yaml";

export interface ColumnDef {
  key: string;
  header: string;
  width?: number;
  formatter?: (value: unknown) => string;
}

function extractValue(obj: Record<string, unknown>, key: string): unknown {
  const parts = key.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current === null || current === undefined) return "";
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function formatTable(
  data: Record<string, unknown>[],
  columns: ColumnDef[]
): string {
  const table = new Table({
    head: columns.map((c) => c.header),
    style: { head: ["cyan"], border: ["gray"] },
    ...(columns.some((c) => c.width)
      ? { colWidths: columns.map((c) => c.width ?? null) }
      : {}),
  });

  for (const row of data) {
    const cells = columns.map((col) => {
      const raw = extractValue(row, col.key);
      return col.formatter ? col.formatter(raw) : formatValue(raw);
    });
    table.push(cells);
  }

  return table.toString();
}

export function formatJson(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

export function formatYaml(data: unknown): string {
  return yaml.dump(data, { indent: 2, lineWidth: 120, noRefs: true });
}

export function output(
  data: unknown,
  format: OutputFormat,
  columns?: ColumnDef[]
): void {
  switch (format) {
    case "json":
      console.log(formatJson(data));
      break;
    case "yaml":
      console.log(formatYaml(data));
      break;
    case "table": {
      if (!Array.isArray(data)) {
        const record = data as Record<string, unknown>;
        const entries = Object.entries(record);
        const detailTable = new Table({
          style: { head: ["cyan"], border: ["gray"] },
        });
        for (const [key, value] of entries) {
          detailTable.push({ [key]: formatValue(value) });
        }
        console.log(detailTable.toString());
        break;
      }
      if (!columns) {
        if (data.length === 0) {
          console.log("No results found.");
          return;
        }
        const firstItem = data[0] as Record<string, unknown>;
        columns = Object.keys(firstItem).map((key) => ({
          key,
          header: key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " "),
        }));
      }
      if (data.length === 0) {
        console.log("No results found.");
        return;
      }
      console.log(formatTable(data as Record<string, unknown>[], columns));
      break;
    }
  }
}

export function outputSingle(
  data: Record<string, unknown>,
  format: OutputFormat
): void {
  if (format === "json") {
    console.log(formatJson(data));
  } else if (format === "yaml") {
    console.log(formatYaml(data));
  } else {
    const table = new Table({
      style: { head: ["cyan"], border: ["gray"] },
    });
    for (const [key, value] of Object.entries(data)) {
      const label = key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " ");
      table.push({ [label]: formatValue(value) });
    }
    console.log(table.toString());
  }
}
