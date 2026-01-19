import { useMemo, useState } from "react";
import * as XLSX from "xlsx";
import * as XLSXStyle from "xlsx-js-style";
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

  const readSpreadsheetFile = async (file: File) => {
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

  const handleCombinedUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    setSheetPreview(null);
    setSheetError("");
    setExtractState({ loading: false, error: "", data: null });
    if (files.length === 0) {
      return;
    }

    const isPdf = (file: File) =>
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    const isSpreadsheet = (file: File) => {
      const name = file.name.toLowerCase();
      return (
        name.endsWith(".xlsx") ||
        name.endsWith(".xls") ||
        file.type ===
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
        file.type === "application/vnd.ms-excel"
      );
    };

    const pdfs = files.filter(isPdf);
    const sheetFile = files.find(isSpreadsheet) ?? null;

    if (files.filter(isSpreadsheet).length > 1) {
      setSheetError("Please upload only one spreadsheet.");
    }

    if (sheetFile) {
      await readSpreadsheetFile(sheetFile);
    } else {
      setSheetError("Include a spreadsheet (.xlsx or .xls).");
    }

    if (pdfs.length === 0) {
      setExtractState({
        loading: false,
        error: "Add at least one PDF file to extract metadata.",
        data: null,
      });
      return;
    }

    setExtractState({ loading: true, error: "", data: null });
    try {
      const data = await extractFiles(pdfs);
      setExtractState({ loading: false, error: "", data });
    } catch (error) {
      setExtractState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to extract.",
        data: null,
      });
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

  const displaySheet = useMemo(() => {
    if (!sheetPreview) {
      return null;
    }
    const totalCols = sheetPreview.headers.length;
    if (totalCols === 0) {
      return { headers: [], rows: [], upcIndex: -1 };
    }
    if (sheetIndices.upc < 0) {
      return {
        headers: sheetPreview.headers,
        rows: sheetPreview.rows,
        upcIndex: sheetIndices.upc,
      };
    }
    const hasValue = (colIndex: number) =>
      sheetPreview.rows.some((row) => (row[colIndex] ?? "").trim());
    const keepIndices = Array.from({ length: totalCols }, (_, index) => index).filter(
      (index) =>
        index <= sheetIndices.upc ||
        (sheetPreview.headers[index] ?? "").trim() ||
        hasValue(index)
    );
    const headers = keepIndices.map((index) => sheetPreview.headers[index] ?? "");
    const rows = sheetPreview.rows.map((row) => keepIndices.map((index) => row[index] ?? ""));
    return {
      headers,
      rows,
      upcIndex: keepIndices.indexOf(sheetIndices.upc),
    };
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

  const careLabelsNormalized = useMemo(
    () =>
      extractState.data?.care_labels.map((item) => ({
        upc: String(item.upc ?? ""),
        size: String(item.size ?? "").toUpperCase(),
        color: String(item.color ?? "").toUpperCase(),
      })) ?? [],
    [extractState.data]
  );

  const hangTagsNormalized = useMemo(
    () =>
      extractState.data?.hang_tags.map((item) => ({
        upc: String(item.upc ?? ""),
        size: String(item.size ?? "").toUpperCase(),
        color: String(item.color ?? "").toUpperCase(),
      })) ?? [],
    [extractState.data]
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

  const upcToCareLabels = useMemo(() => {
    const map = new Map<string, typeof careLabelsNormalized>();
    careLabelsNormalized.forEach((row) => {
      if (!row.upc) {
        return;
      }
      const list = map.get(row.upc) ?? [];
      list.push(row);
      map.set(row.upc, list);
    });
    return map;
  }, [careLabelsNormalized]);

  const upcToHangTags = useMemo(() => {
    const map = new Map<string, typeof hangTagsNormalized>();
    hangTagsNormalized.forEach((row) => {
      if (!row.upc) {
        return;
      }
      const list = map.get(row.upc) ?? [];
      list.push(row);
      map.set(row.upc, list);
    });
    return map;
  }, [hangTagsNormalized]);

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

  const rowFill = (status: "missing" | "mismatch" | "match") => {
    if (status === "match") {
      return "E7F6EC";
    }
    if (status === "mismatch") {
      return "FDE8E8";
    }
    return "FFF4E5";
  };

  const mismatchFill = "F9CACA";

  const applyCellStyle = (worksheet: any, cellAddress: string, fillColor: string) => {
    const cell = worksheet[cellAddress];
    if (!cell) {
      return;
    }
    cell.s = {
      fill: {
        fgColor: { rgb: fillColor },
      },
    };
  };

  const exportExtracted = () => {
    const headers = ["Type", "Style", "Size", "Color", "UPC"];
    const rows = mergedItems.map((item) => [
      item.type ?? "",
      item.style_number ?? "",
      item.size ?? "",
      item.color ?? "",
      item.upc ?? "",
    ]);
    const sheet = XLSXStyle.utils.aoa_to_sheet([headers, ...rows]);
    rows.forEach((row, index) => {
      const status = matchStatus(
        String(row[4] ?? ""),
        String(row[2] ?? "").toUpperCase(),
        String(row[3] ?? "").toUpperCase(),
        upcToSheetRows.get(String(row[4] ?? "")) ?? []
      );
      const fill = rowFill(status.status as "missing" | "mismatch" | "match");
      for (let c = 0; c < headers.length; c += 1) {
        const addr = XLSXStyle.utils.encode_cell({ r: index + 1, c });
        applyCellStyle(sheet, addr, fill);
      }
      if (status.status === "mismatch") {
        if (!status.sizeMatch) {
          applyCellStyle(sheet, XLSXStyle.utils.encode_cell({ r: index + 1, c: 2 }), mismatchFill);
        }
        if (!status.colorMatch) {
          applyCellStyle(sheet, XLSXStyle.utils.encode_cell({ r: index + 1, c: 3 }), mismatchFill);
        }
      }
    });
    const workbook = XLSXStyle.utils.book_new();
    XLSXStyle.utils.book_append_sheet(workbook, sheet, "Extracted");
    XLSXStyle.writeFile(workbook, "extracted_items.xlsx");
  };

  const exportSpreadsheetPreview = () => {
    if (!sheetPreview) {
      return;
    }
    const baseHeaders = displaySheet?.headers ?? sheetPreview.headers;
    const baseRows = displaySheet?.rows ?? sheetPreview.rows;
    const headers = [...baseHeaders, "Care Label", "Hang Tag"];
    const rows = sheetRowsNormalized.map((row, index) => {
      const careStatus = matchStatus(
        row.upc,
        row.size,
        row.color,
        upcToCareLabels.get(row.upc) ?? []
      );
      const hangStatus = matchStatus(
        row.upc,
        row.size,
        row.color,
        upcToHangTags.get(row.upc) ?? []
      );
      const careLabel =
        careStatus.status === "match"
          ? "Match"
          : careStatus.status === "mismatch"
          ? "Mismatch"
          : "Not found";
      const hangTag =
        hangStatus.status === "match"
          ? "Match"
          : hangStatus.status === "mismatch"
          ? "Mismatch"
          : "Not found";
      return [...(baseRows[index] ?? []), careLabel, hangTag];
    });
    const sheet = XLSXStyle.utils.aoa_to_sheet([headers, ...rows]);
    rows.forEach((row, index) => {
      const careStatus = matchStatus(
        sheetRowsNormalized[index].upc,
        sheetRowsNormalized[index].size,
        sheetRowsNormalized[index].color,
        upcToCareLabels.get(sheetRowsNormalized[index].upc) ?? []
      );
      const hangStatus = matchStatus(
        sheetRowsNormalized[index].upc,
        sheetRowsNormalized[index].size,
        sheetRowsNormalized[index].color,
        upcToHangTags.get(sheetRowsNormalized[index].upc) ?? []
      );
      const careFill = rowFill(careStatus.status as "missing" | "mismatch" | "match");
      const hangFill = rowFill(hangStatus.status as "missing" | "mismatch" | "match");
      const careAddr = XLSXStyle.utils.encode_cell({ r: index + 1, c: headers.length - 2 });
      const hangAddr = XLSXStyle.utils.encode_cell({ r: index + 1, c: headers.length - 1 });
      applyCellStyle(sheet, careAddr, careFill);
      applyCellStyle(sheet, hangAddr, hangFill);
    });
    const workbook = XLSXStyle.utils.book_new();
    XLSXStyle.utils.book_append_sheet(workbook, sheet, "Spreadsheet");
    XLSXStyle.writeFile(workbook, "spreadsheet_preview.xlsx");
  };

  return (
    <div className="container">
      <h1>UPC Validator POC</h1>
      <p>
        Upload care label and RFID PDFs with the spreadsheet. Extraction and validation
        start automatically.
      </p>
      <input
        type="file"
        accept=".pdf,.xlsx,.xls,application/pdf"
        multiple
        onChange={handleCombinedUpload}
      />
      {extractState.loading && (
        <div className="loader" role="status" aria-live="polite">
          <div className="loader-bar" />
          <span>Extracting and validating…</span>
        </div>
      )}
      {extractState.data && sheetPreview && (
        <button type="button" onClick={exportSpreadsheetPreview}>
          Export to Excel
        </button>
      )}
      {extractState.data && displaySheet && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                {displaySheet.headers.map((header, index) => (
                  <th
                    key={`${header}-${index}`}
                    className={index === displaySheet.upcIndex ? "upc-column" : ""}
                  >
                    {header}
                  </th>
                ))}
                <th>Care Label</th>
                <th>Hang Tag</th>
              </tr>
            </thead>
            <tbody>
              {sheetRowsNormalized.map((row, rowIndex) => {
                const careStatus = matchStatus(
                  row.upc,
                  row.size,
                  row.color,
                  upcToCareLabels.get(row.upc) ?? []
                );
                const hangStatus = matchStatus(
                  row.upc,
                  row.size,
                  row.color,
                  upcToHangTags.get(row.upc) ?? []
                );
                return (
                  <tr key={`row-${rowIndex}`}>
                    {(displaySheet.rows[rowIndex] ?? []).map((cell, cellIndex) => (
                      <td
                        key={`cell-${rowIndex}-${cellIndex}`}
                        className={cellIndex === displaySheet.upcIndex ? "upc-column" : ""}
                      >
                        {cell}
                      </td>
                    ))}
                    <td className={`row-${careStatus.status}`}>
                      {careStatus.status === "match"
                        ? "Match"
                        : careStatus.status === "mismatch"
                        ? "Mismatch"
                        : "Not found"}
                    </td>
                    <td className={`row-${hangStatus.status}`}>
                      {hangStatus.status === "match"
                        ? "Match"
                        : hangStatus.status === "mismatch"
                        ? "Mismatch"
                        : "Not found"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
