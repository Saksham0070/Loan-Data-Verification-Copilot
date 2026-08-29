import fs from "node:fs/promises";
import path from "node:path";
import { Workbook } from "@oai/artifact-tool";

const dataDir = "D:\\Loan Data Verification Copilot\\data";

const fields = [
  "loan_id", "borrower_id", "loan_type", "origination_date", "maturity_date",
  "original_principal", "current_balance", "interest_rate", "term_months",
  "borrower_state", "loan_purpose", "credit_grade", "employment_length",
  "income_band", "payment_status", "days_past_due", "servicer_name",
  "last_payment_date", "last_updated_at", "document_status", "source_system",
];

const primaryRows = [
  ["LN-30001", "BR-30001", "PERSONAL", "2024-01-15", "2028-01-15", 10000, 8500, 8.5, 48, "CA", "DEBT_CONSOLIDATION", "A", 5, "50K_75K", "ACTIVE", 0, "Demo Servicer", "2026-08-15", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30002", "BR-30002", "AUTO", "2023-06-01", "2028-06-01", 25000, 19000, 6.2, 60, "TX", "AUTO_PURCHASE", "B", 7, "75K_100K", "CURRENT", 0, "Demo Servicer", "2026-08-11", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["", "BR-30003", "PERSONAL", "2024-02-01", "2027-02-01", 5000, 4200, 12, 36, "NY", "MEDICAL", "C", 3, "25K_50K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30004", "BR-30004", "PERSONAL", "2024-03-01", "2027-03-01", 7000, 6000, 9, 36, "FL", "HOME_IMPROVEMENT", "B", 4, "50K_75K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30004", "BR-30005", "PERSONAL", "2024-03-01", "2027-03-01", 7000, 6000, 9, 36, "FL", "HOME_IMPROVEMENT", "B", 4, "50K_75K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30005", "BR-30006", "PERSONAL", "2024-04-01", "2027-04-01", 12000, 10000, 10, 36, "IL", "DEBT_CONSOLIDATION", "C", 2, "25K_50K", "ACTIVE", 0, "Demo Servicer", "2026-08-08", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30006", "BR-30006", "PERSONAL", "2024-04-01", "2027-04-01", 12000, 10000, 10, 36, "IL", "DEBT_CONSOLIDATION", "C", 2, "25K_50K", "ACTIVE", 0, "Demo Servicer", "2026-08-08", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30007", "BR-30007", "PERSONAL", "2024-13-40", "2027-05-01", 8000, 6500, 11, 36, "WA", "MEDICAL", "B", 6, "75K_100K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30008", "BR-30008", "AUTO", "2025-08-01", "2024-08-01", 18000, 12000, 7, 60, "OH", "AUTO_PURCHASE", "A", 8, "100K_PLUS", "CURRENT", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30009", "BR-30009", "PERSONAL", "2024-06-01", "2027-06-01", -5000, -100, 8, 36, "CA", "DEBT_CONSOLIDATION", "B", 5, "50K_75K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30010", "BR-30010", "PERSONAL", "2024-07-01", "2027-07-01", 10000, 12000, 125, 36, "NV", "HOME_IMPROVEMENT", "C", 1, "25K_50K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30011", "BR-30011", "PERSONAL", "2024-08-01", "2027-08-01", 9000, 7500, 12, 36, "GA", "MEDICAL", "D", 2, "25K_50K", "DEFAULTED", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30012", "BR-30012", "PERSONAL", "2024-09-01", "2027-09-01", 11000, 9000, 7.5, 36, "PA", "DEBT_CONSOLIDATION", "B", 9, "75K_100K", "CURRENT", 15, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-30013", "BR-30013", "PERSONAL", "2024-10-01", "2027-10-01", 4000, 3000, 14, 36, "CA", "MEDICAL", "C", 2, "25K_50K", "ACTIVE", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "", "ORIGINATION_API"],
  ["LN-30014", "BR-30014", "PERSONAL", "2024-11-01", "2027-11-01", 6000, 4500, 9, 36, "ZZ", "HOME_IMPROVEMENT", "B", 4, "50K_75K", "ACTIVE", 0, "Demo Servicer", "2024-01-05", "2024-01-10", "COMPLETE", "ORIGINATION_API"],
  ["LN-30015", "BR-30015", "PERSONAL", "2024-12-01", "2027-12-01", 15000, 1000, 8, 36, "MI", "DEBT_CONSOLIDATION", "A", 6, "75K_100K", "CLOSED", 0, "Demo Servicer", "2026-08-10", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
];

const servicerRows = [
  ["loan_id", "current_balance", "payment_status", "last_updated_at", "source_system"],
  ["LN-30001", 8300, "ACTIVE", "2026-08-28", "SERVICER_PORTAL"],
  ["LN-30002", 19000, "DELINQUENT", "2026-08-28", "SERVICER_PORTAL"],
  ["LN-30015", 0, "PAID_OFF", "2026-08-28", "SERVICER_PORTAL"],
  ["LN-99999", 5000, "ACTIVE", "2026-08-28", "SERVICER_PORTAL"],
];

const documentRows = [
  ["loan_id", "document_status", "last_updated_at", "source_system"],
  ["LN-30001", "COMPLETE", "2026-08-28", "DOCUMENT_REPOSITORY"],
  ["LN-30002", "PENDING", "2026-08-28", "DOCUMENT_REPOSITORY"],
  ["LN-30013", "COMPLETE", "2026-08-28", "DOCUMENT_REPOSITORY"],
  ["LN-30015", "COMPLETE", "2026-08-28", "DOCUMENT_REPOSITORY"],
];

const cleanRows = [
  ["LN-40001", "BR-40001", "PERSONAL", "2024-01-01", "2027-01-01", 10000, 7800, 7.5, 36, "CA", "DEBT_CONSOLIDATION", "A", 5, "75K_100K", "ACTIVE", 0, "Demo Servicer", "2026-08-15", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
  ["LN-40002", "BR-40002", "AUTO", "2024-02-01", "2029-02-01", 30000, 24000, 5.9, 60, "TX", "AUTO_PURCHASE", "A", 8, "100K_PLUS", "CURRENT", 0, "Demo Servicer", "2026-08-14", "2026-08-20", "COMPLETE", "ORIGINATION_API"],
];

function toCsv(rows) {
  return rows
    .map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\r\n") + "\r\n";
}

async function writeAndVerify(filename, rows, expectedHeaders) {
  const text = toCsv(rows);
  const outputPath = path.join(dataDir, filename);
  await fs.writeFile(outputPath, text, "utf8");
  const workbook = await Workbook.fromCSV(text, { sheetName: "Fixture" });
  const inspection = await workbook.inspect({
    kind: "table",
    range: `Fixture!A1:U${rows.length}`,
    include: "values",
    tableMaxRows: 3,
    tableMaxCols: 25,
  });
  if (!inspection.ndjson.includes(expectedHeaders[0]) || !inspection.ndjson.includes(expectedHeaders.at(-1))) {
    throw new Error(`${filename} did not retain its required headers.`);
  }
}

await writeAndVerify("hackathon_test_loan_tape.csv", [fields, ...primaryRows], fields);
await writeAndVerify("hackathon_test_servicer_update.csv", servicerRows, servicerRows[0]);
await writeAndVerify("hackathon_test_document_manifest.csv", documentRows, documentRows[0]);
await writeAndVerify("hackathon_test_clean_loans.csv", [fields, ...cleanRows], fields);

console.log("Created and verified 4 CSV test fixtures in the data folder.");
