import {apiFetch} from './api';
import {SERVER_BASE_URL} from '../config';
import {getAccessToken} from '../storage/tokenStorage';

// ── Response types ─────────────────────────────────────────────────────────────
// Matches server/app/api/files.py response shapes

export type FileScope = 'personal' | 'department' | 'company';

export interface ArtifactItem {
  id: string;
  filename: string;
  file_type: string;
  download_url: string | null;
  created_at: string;
  file_size?: string;
  scope: FileScope;
  folder_id: string | null;
}

export interface FilesResponse {
  artifacts: ArtifactItem[];
  count: number;
}

export interface UploadResponse {
  artifact_id: string;
  filename: string;
  file_type: string;
  scope: FileScope;
  size_bytes: number;
  download_url: string | null;
}

// ── API functions ──────────────────────────────────────────────────────────────

/** List files for a given scope, optionally inside a folder. */
export const listFilesApi = (
  scope: FileScope = 'personal',
  folderId?: string | null,
): Promise<FilesResponse> => {
  let url = `/files/?scope=${encodeURIComponent(scope)}`;
  if (folderId) { url += `&folder_id=${encodeURIComponent(folderId)}`; }
  return apiFetch<FilesResponse>(url);
};

/** Upload a file to a specific scope (and optionally into a folder). */
export const uploadFileApi = (
  fileUri: string,
  fileName: string,
  mimeType: string,
  scope: FileScope = 'personal',
  folderId?: string | null,
): Promise<UploadResponse> => {
  const form = new FormData();
  form.append('media_file', {uri: fileUri, name: fileName, type: mimeType} as unknown as Blob);
  form.append('scope', scope);
  if (folderId) { form.append('folder_id', folderId); }
  return apiFetch<UploadResponse>('/files/upload', {method: 'POST', body: form});
};

export const deleteFileApi = (id: string): Promise<{deleted: boolean}> =>
  apiFetch<{deleted: boolean}>(`/files/${id}`, {method: 'DELETE'});

export interface MoveFileResponse {
  moved: boolean;
  artifact_id: string;
  folder_id: string | null;
}

/** Move a file to a different folder (or to root if folderId=null). */
export const moveFileApi = (
  fileId: string,
  folderId: string | null,
): Promise<MoveFileResponse> =>
  apiFetch<MoveFileResponse>(`/files/${fileId}/move`, {
    method: 'PATCH',
    body: JSON.stringify({folder_id: folderId}),
    headers: {'Content-Type': 'application/json'},
  });

// GET /files/{id} returns raw file bytes (FileResponse — not JSON).
// Returns a clean URL — callers must pass Authorization header via getDownloadHeaders().
export const getFileDownloadUrl = (id: string): string =>
  `${SERVER_BASE_URL}/files/${id}`;

export const getDownloadHeaders = async (): Promise<Record<string, string>> => {
  const token = await getAccessToken();
  return token ? {Authorization: `Bearer ${token}`} : {};
};
