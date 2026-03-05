import {apiFetch} from './api';
import {FileScope} from './files';

// ── Types ──────────────────────────────────────────────────────────────────────

export interface FolderItem {
  id: string;
  name: string;
  scope: FileScope;
  department?: string | null;
  created_at: string;
}

export interface FoldersResponse {
  folders: FolderItem[];
  count: number;
}

// ── API functions ──────────────────────────────────────────────────────────────

export const listFoldersApi = (scope: FileScope): Promise<FoldersResponse> =>
  apiFetch<FoldersResponse>(`/folders/?scope=${scope}`);

export const createFolderApi = (
  name: string,
  scope: FileScope,
): Promise<FolderItem> =>
  apiFetch<FolderItem>('/folders/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, scope}),
  });

export const renameFolderApi = (
  id: string,
  name: string,
): Promise<FolderItem> =>
  apiFetch<FolderItem>(`/folders/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name}),
  });

export const deleteFolderApi = (id: string): Promise<{deleted: boolean}> =>
  apiFetch<{deleted: boolean}>(`/folders/${id}`, {method: 'DELETE'});
