export type ExtractResponse = {
  care_labels: Array<Record<string, unknown>>;
  hang_tags: Array<Record<string, unknown>>;
};

export type ValidationResponse = {
  summary: {
    rows: number;
    care_label_matches: number;
    hang_tag_matches: number;
  };
  results: Array<Record<string, unknown>>;
};

const API_BASE = "http://localhost:8000";

export async function extractFiles(files: FileList): Promise<ExtractResponse> {
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

export async function validateSpreadsheet(
  spreadsheet: File,
  metadata: ExtractResponse
): Promise<ValidationResponse> {
  const formData = new FormData();
  formData.append("spreadsheet", spreadsheet);
  formData.append("metadata_json", JSON.stringify(metadata));
  const response = await fetch(`${API_BASE}/validate`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
