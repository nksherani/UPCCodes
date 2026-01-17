import { useMemo, useState } from "react";

type ExtractedImage = {
  image_id: string;
  page: number;
  index: number;
  format: string;
  width: number;
  height: number;
  data_base64: string;
  ocr_text: string;
  source?: "embedded" | "page_render";
  note?: string;
};

type ExtractResponse = {
  pdf_text: string;
  images: ExtractedImage[];
  file_name?: string;
  created_at?: string;
  id?: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ExtractResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const totalImages = useMemo(() => result?.images.length ?? 0, [result]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Please choose a PDF file.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/extract`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "Upload failed.");
      }

      const data = (await response.json()) as ExtractResponse;
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header>
        <h1>PDF Extractor</h1>
        <p>Upload a PDF to extract text, images, and OCR results.</p>
      </header>

      <form className="upload-form" onSubmit={handleSubmit}>
        <input
          type="file"
          accept="application/pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Processing..." : "Upload PDF"}
        </button>
      </form>

      {error && <div className="error">{error}</div>}

      {result && (
        <section className="results">
          <div className="meta">
            <div>
              <strong>File:</strong> {result.file_name ?? "Unnamed"}
            </div>
            <div>
              <strong>Created:</strong> {result.created_at ?? "n/a"}
            </div>
            <div>
              <strong>Images:</strong> {totalImages}
            </div>
            {result.id && (
              <div>
                <strong>Mongo ID:</strong> {result.id}
              </div>
            )}
          </div>

          <div className="panel">
            <h2>Extracted Text</h2>
            <pre>{result.pdf_text || "No text extracted."}</pre>
          </div>

          <div className="panel">
            <h2>Images + OCR</h2>
            {result.images.length === 0 && <p>No images extracted.</p>}
            <div className="images-grid">
              {result.images.map((image) => (
                <div key={image.image_id} className="image-card">
                  <img
                    src={`data:image/${image.format};base64,${image.data_base64}`}
                    alt={`Page ${image.page} image ${image.index}`}
                  />
                  <div className="image-meta">
                    <div>
                      <strong>ID:</strong> {image.image_id}
                    </div>
                    <div>
                      <strong>Page:</strong> {image.page}
                    </div>
                    <div>
                      <strong>Size:</strong> {image.width}x{image.height}
                    </div>
                    {image.source && (
                      <div>
                        <strong>Source:</strong> {image.source}
                      </div>
                    )}
                  </div>
                  <div className="ocr">
                    <strong>OCR Text</strong>
                    <pre>{image.ocr_text || "No OCR text found."}</pre>
                  </div>
                  {image.note && <div className="note">{image.note}</div>}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
