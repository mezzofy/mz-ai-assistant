export type ViewerType = 'image' | 'video' | 'text' | 'markdown' | null;

const IMAGE_EXTS    = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']);
const VIDEO_EXTS    = new Set(['mp4', 'mov', 'avi', 'mkv', 'm4v']);
const MARKDOWN_EXTS = new Set(['md', 'markdown']);
const TEXT_EXTS     = new Set(['txt', 'log', 'json', 'yaml', 'yml', 'xml', 'csv', 'py', 'js', 'ts']);
const EXCLUDED_EXTS = new Set(['pdf', 'pptx', 'ppt', 'docx', 'doc', 'xls', 'xlsx']);

export function getViewerType(filename: string, mimeType?: string): ViewerType {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (EXCLUDED_EXTS.has(ext)) { return null; }
  if (IMAGE_EXTS.has(ext))    { return 'image'; }
  if (VIDEO_EXTS.has(ext))    { return 'video'; }
  if (MARKDOWN_EXTS.has(ext)) { return 'markdown'; }
  if (TEXT_EXTS.has(ext))     { return 'text'; }
  // MIME fallback for extensionless files
  if (mimeType) {
    const m = mimeType.toLowerCase();
    if (m.startsWith('image/'))  { return 'image'; }
    if (m.startsWith('video/'))  { return 'video'; }
    if (m === 'text/markdown')   { return 'markdown'; }
    if (m.startsWith('text/'))   { return 'text'; }
  }
  return null;
}
