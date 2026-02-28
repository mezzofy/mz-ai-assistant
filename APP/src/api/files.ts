import {apiFetch} from './api';
import {SERVER_BASE_URL} from '../config';
import {getAccessToken} from '../storage/tokenStorage';

// ── Response types ─────────────────────────────────────────────────────────────
// Matches server/app/api/files.py response shapes

export interface ArtifactItem {
  id: string;
  filename: string;
  file_type: string;
  download_url: string | null;
  created_at: string;
  file_size?: string;
}

export interface FilesResponse {
  artifacts: ArtifactItem[];
  count: number;
}

export interface UploadResponse {
  artifact_id: string;
  filename: string;
  download_url: string | null;
}

// ── API functions ──────────────────────────────────────────────────────────────

export const listFilesApi = (): Promise<FilesResponse> =>
  apiFetch<FilesResponse>('/files/');

export const uploadFileApi = (
  fileUri: string,
  fileName: string,
  mimeType: string,
): Promise<UploadResponse> => {
  const form = new FormData();
  // React Native FormData file: pass object with uri/name/type
  form.append('media_file', {uri: fileUri, name: fileName, type: mimeType} as unknown as Blob);
  return apiFetch<UploadResponse>('/files/upload', {
    method: 'POST',
    body: form,
  });
};

export const deleteFileApi = (id: string): Promise<{deleted: boolean}> =>
  apiFetch<{deleted: boolean}>(`/files/${id}`, {method: 'DELETE'});

// GET /files/{id} returns raw file bytes (FileResponse — not JSON).
// Returns a token-appended URL for direct download via Linking.openURL() or a WebView.
export const getFileDownloadUrl = async (id: string): Promise<string> => {
  const token = await getAccessToken();
  return `${SERVER_BASE_URL}/files/${id}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
};
