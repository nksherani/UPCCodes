import { useState } from "react";
import * as XLSX from "xlsx";
import { extractFiles, validateSpreadsheet } from "./api";

type ExtractState = {
  loading: boolean;
  error: string;
  data: null | Awaited<ReturnType<typeof extractFiles>>;
};

type ValidationState = {
  loading: boolean;
  error: string;
  data: null | Awaited<ReturnType<typeof validateSpreadsheet>>;
};

export default function App() {
  const [pdfFiles, setPdfFiles] = useState<FileList | null>(null);
  const [sheetFile, setSheetFile] = useState<File | null>(null);
  const [sheetPreview, setSheetPreview] = useState<{
    headers: string[];
    rows: string[][];
  } | null>(null);
  const [sheetError, setSheetError] = useState("");
  const [extractState, setExtractState] = useState<ExtractState>({
    loading: false,
    error: "",
    data: null,
  });
  const [validationState, setValidationState] = useState<ValidationState>({
    loading: false,
    error: "",
    data: null,
  });

  const mergedItems =
    extractState.data
      ? [
          ...extractState.data.care_labels.map((item) => ({
            type: "Care Label",
            ...item,
          })),
          ...extractState.data.hang_tags.map((item) => ({
            type: "Hang Tag",
            ...item,
          })),
        ]
      : [];

  const handleExtract = async () => {
    if (!pdfFiles || pdfFiles.length === 0) {
      setExtractState({ loading: false, error: "Select PDF files first.", data: null });
      return;
    }
    setExtractState({ loading: true, error: "", data: null });
    try {
      const data = await extractFiles(pdfFiles);
      setExtractState({ loading: false, error: "", data });
    } catch (error) {
      setExtractState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to extract.",
        data: null,
      });
    }
  };

  const handleValidate = async () => {
    if (!sheetFile) {
      setValidationState({ loading: false, error: "Select an Excel file.", data: null });
      return;
    }
    if (!extractState.data) {
      setValidationState({ loading: false, error: "Run extraction first.", data: null });
      return;
    }
    setValidationState({ loading: true, error: "", data: null });
    try {
      const data = await validateSpreadsheet(sheetFile, extractState.data);
      setValidationState({ loading: false, error: "", data });
    } catch (error) {
      setValidationState({
        loading: false,
        error: error instanceof Error ? error.message : "Validation failed.",
        data: null,
      });
    }
  };

  const handleSheetChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSheetFile(file);
    setSheetPreview(null);
    setSheetError("");
    if (!file) {
      return;
    }
    try {
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: "array" });
      const sheetName = workbook.SheetNames[0];
      if (!sheetName) {
        setSheetError("Spreadsheet has no sheets.");
        return;
      }
      const sheet = workbook.Sheets[sheetName];
      const range = XLSX.utils.decode_range(sheet["!ref"] ?? "A1:A1");
      const formatCell = (rowIndex: number, colIndex: number) => {
        const cell = sheet[XLSX.utils.encode_cell({ r: rowIndex, c: colIndex })];
        if (!cell) {
          return "";
        }
        if (cell.t === "n" && typeof cell.v === "number") {
          return Math.trunc(cell.v).toString();
        }
        return XLSX.utils.format_cell(cell);
      };

      if (range.e.r < range.s.r) {
        setSheetError("Spreadsheet is empty.");
        return;
      }

      const headers = Array.from(
        { length: range.e.c - range.s.c + 1 },
        (_, index) => formatCell(range.s.r, range.s.c + index).trim()
      );
      const normalizedRows: string[][] = [];
      for (let r = range.s.r + 1; r <= range.e.r; r += 1) {
        const row = headers.map((_, index) =>
          formatCell(r, range.s.c + index).trim()
        );
        if (row.some((cell) => cell)) {
          normalizedRows.push(row);
        }
      }
      setSheetPreview({ headers, rows: normalizedRows.slice(0, 50) });
    } catch (error) {
      setSheetError(error instanceof Error ? error.message : "Failed to read spreadsheet.");
    }
  };

  return (
    <div className="container">
      <header>
        <h1>UPC Validator POC</h1>
        <p>
          Upload care label and RFID PDFs, extract metadata, then validate against a
          spreadsheet.
        </p>
      </header>

      <section className="card">
        <h2>1. Upload PDF Files</h2>
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={(event) => setPdfFiles(event.target.files)}
        />
        <button onClick={handleExtract} disabled={extractState.loading}>
          {extractState.loading ? "Extracting..." : "Extract Metadata"}
        </button>
        {extractState.error && <p className="error">{extractState.error}</p>}
        {extractState.data && (
          <div className="summary">
            <p>
              Care labels: {extractState.data.care_labels.length} | Hang tags:{" "}
              {extractState.data.hang_tags.length}
            </p>
          </div>
        )}
      </section>

      {extractState.data && (
        <section className="card">
          <h2>Extracted Items</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Style</th>
                  <th>Size</th>
                  <th>Color</th>
                  <th>UPC</th>
                </tr>
              </thead>
              <tbody>
                {mergedItems.map((item, index) => (
                  <tr key={`${item.type}-${index}`}>
                    <td>{item.type}</td>
                    <td>{item.style_number as string}</td>
                    <td>{item.size as string}</td>
                    <td>{item.color as string}</td>
                    <td>{item.upc as string}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card">
        <h2>2. Upload Spreadsheet</h2>
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={handleSheetChange}
        />
        {sheetError && <p className="error">{sheetError}</p>}
        {sheetPreview && (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  {sheetPreview.headers.map((header, index) => (
                    <th key={`${header}-${index}`}>{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sheetPreview.rows.map((row, rowIndex) => (
                  <tr key={`row-${rowIndex}`}>
                    {row.map((cell, cellIndex) => (
                      <td key={`cell-${rowIndex}-${cellIndex}`}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <button onClick={handleValidate} disabled={validationState.loading}>
          {validationState.loading ? "Validating..." : "Validate UPCs"}
        </button>
        {validationState.error && <p className="error">{validationState.error}</p>}
        {validationState.data && (
          <div className="summary">
            <p>Rows validated: {validationState.data.summary.rows}</p>
            <p>
              Care label matches: {validationState.data.summary.care_label_matches} | Hang
              tag matches: {validationState.data.summary.hang_tag_matches}
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
