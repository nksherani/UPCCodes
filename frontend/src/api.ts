export type ExtractResponse = {
  care_labels: Array<Record<string, unknown>>;
  hang_tags: Array<Record<string, unknown>>;
};

const API_BASE = "http://localhost:8000";

export async function extractFiles(files: FileList | File[]): Promise<ExtractResponse> {
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
