import { useState } from "react";
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
              Files processed: {extractState.data.files.length}
            </p>
            <p>
              Care labels: {extractState.data.normalized.care_labels.length} | Hang tags:{" "}
              {extractState.data.normalized.hang_tags.length}
            </p>
          </div>
        )}
      </section>

      <section className="card">
        <h2>2. Upload Spreadsheet</h2>
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={(event) => setSheetFile(event.target.files?.[0] ?? null)}
        />
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
