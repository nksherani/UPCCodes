import { useMemo, useState } from "react";
import * as XLSX from "xlsx";
import { extractFiles } from "./api";

type ExtractState = {
  loading: boolean;
  error: string;
  data: null | Awaited<ReturnType<typeof extractFiles>>;
};

type ItemRow = {
  type: string;
  style_number?: string;
  size?: string;
  color?: string;
  upc?: string;
  [key: string]: unknown;
};

export default function App() {
  const [pdfFiles, setPdfFiles] = useState<FileList | null>(null);
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

  const mergedItems: ItemRow[] =
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
        ].map((item) => item as ItemRow)
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

  const handleSheetChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
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

  const sheetIndices = useMemo(() => {
    if (!sheetPreview) {
      return { upc: -1, size: -1, color: -1 };
    }
    const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
    const headers = sheetPreview.headers.map(normalize);
    const findIndex = (candidates: string[]) =>
      headers.findIndex((header) => candidates.some((candidate) => header.includes(candidate)));
    return {
      upc: findIndex(["carelabelupc", "careupc", "hangtagupc", "rfidupc", "upc"]),
      size: findIndex(["size"]),
      color: findIndex(["color"]),
    };
  }, [sheetPreview]);

  const sheetRowsNormalized = useMemo(() => {
    if (!sheetPreview) {
      return [];
    }
    const getCell = (row: string[], index: number) =>
      index >= 0 ? (row[index] ?? "").trim() : "";
    return sheetPreview.rows.map((row) => ({
      upc: getCell(row, sheetIndices.upc),
      size: getCell(row, sheetIndices.size).toUpperCase(),
      color: getCell(row, sheetIndices.color).toUpperCase(),
      row,
    }));
  }, [sheetPreview, sheetIndices]);

  const extractedNormalized = useMemo(
    () =>
      mergedItems.map((item) => ({
        upc: String(item.upc ?? ""),
        size: String(item.size ?? "").toUpperCase(),
        color: String(item.color ?? "").toUpperCase(),
        item,
      })),
    [mergedItems]
  );

  const upcToSheetRows = useMemo(() => {
    const map = new Map<string, typeof sheetRowsNormalized>();
    sheetRowsNormalized.forEach((row) => {
      if (!row.upc) {
        return;
      }
      const list = map.get(row.upc) ?? [];
      list.push(row);
      map.set(row.upc, list);
    });
    return map;
  }, [sheetRowsNormalized]);

  const upcToExtracted = useMemo(() => {
    const map = new Map<string, typeof extractedNormalized>();
    extractedNormalized.forEach((row) => {
      if (!row.upc) {
        return;
      }
      const list = map.get(row.upc) ?? [];
      list.push(row);
      map.set(row.upc, list);
    });
    return map;
  }, [extractedNormalized]);

  const matchStatus = (
    upc: string,
    size: string,
    color: string,
    otherRows: Array<{ size: string; color: string }>
  ) => {
    if (!upc) {
      return { status: "missing", sizeMatch: false, colorMatch: false };
    }
    if (otherRows.length === 0) {
      return { status: "missing", sizeMatch: false, colorMatch: false };
    }
    const exact = otherRows.find((row) => row.size === size && row.color === color);
    if (exact) {
      return { status: "match", sizeMatch: true, colorMatch: true };
    }
    const sizeMatch = otherRows.some((row) => row.size === size);
    const colorMatch = otherRows.some((row) => row.color === color);
    return { status: "mismatch", sizeMatch, colorMatch };
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
                {mergedItems.map((item, index) => {
                  const status = matchStatus(
                    String(item.upc ?? ""),
                    String(item.size ?? "").toUpperCase(),
                    String(item.color ?? "").toUpperCase(),
                    upcToSheetRows.get(String(item.upc ?? "")) ?? []
                  );
                  return (
                    <tr key={`${item.type}-${index}`} className={`row-${status.status}`}>
                    <td>{item.type}</td>
                    <td>{item.style_number as string}</td>
                    <td
                      className={
                        status.status === "mismatch" && !status.sizeMatch ? "cell-mismatch" : ""
                      }
                    >
                      {item.size as string}
                    </td>
                    <td
                      className={
                        status.status === "mismatch" && !status.colorMatch ? "cell-mismatch" : ""
                      }
                    >
                      {item.color as string}
                    </td>
                    <td>{item.upc as string}</td>
                  </tr>
                  );
                })}
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
                {sheetRowsNormalized.map((row, rowIndex) => {
                  const status = matchStatus(
                    row.upc,
                    row.size,
                    row.color,
                    upcToExtracted.get(row.upc) ?? []
                  );
                  return (
                    <tr key={`row-${rowIndex}`} className={`row-${status.status}`}>
                      {row.row.map((cell, cellIndex) => {
                        const isSize = cellIndex === sheetIndices.size;
                        const isColor = cellIndex === sheetIndices.color;
                        const mismatch =
                          status.status === "mismatch" &&
                          ((isSize && !status.sizeMatch) || (isColor && !status.colorMatch));
                        return (
                          <td
                            key={`cell-${rowIndex}-${cellIndex}`}
                            className={mismatch ? "cell-mismatch" : ""}
                          >
                            {cell}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
