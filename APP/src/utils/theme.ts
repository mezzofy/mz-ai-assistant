export const BRAND = {
  primary: '#0A1628',
  secondary: '#1B2B44',
  accent: '#f97316',
  accentGlow: 'rgba(249,115,22,0.15)',
  accentSoft: '#f9731622',
  surface: '#0F1F35',
  surfaceLight: '#162A45',
  card: '#1A2F4D',
  border: '#1E3A5F',
  text: '#E8F0F8',
  textMuted: '#7A8FA6',
  textDim: '#4A6280',
  white: '#FFFFFF',
  danger: '#FF4B6E',
  warning: '#FFB84D',
  success: '#00D4AA',
  info: '#4DA6FF',
  deptColors: {
    finance: '#FFB84D',
    sales: '#00D4AA',
    marketing: '#C77DFF',
    support: '#4DA6FF',
    management: '#FF6B8A',
  } as Record<string, string>,
};

export type ThemeColors = typeof BRAND;

export const LIGHT_THEME: ThemeColors = {
  primary: '#FFFFFF',
  secondary: '#F3F4F6',
  accent: '#f97316',
  accentGlow: 'rgba(249,115,22,0.15)',
  accentSoft: '#f9731622',
  surface: '#F9FAFB',
  surfaceLight: '#F3F4F6',
  card: '#FFFFFF',
  border: '#E5E7EB',
  text: '#111827',
  textMuted: '#6B7280',
  textDim: '#9CA3AF',
  white: '#FFFFFF',
  danger: '#FF4B6E',
  warning: '#FFB84D',
  success: '#00D4AA',
  info: '#4DA6FF',
  deptColors: {
    finance: '#FFB84D',
    sales: '#00D4AA',
    marketing: '#C77DFF',
    support: '#4DA6FF',
    management: '#FF6B8A',
  } as Record<string, string>,
};

export const INPUT_MODES = [
  {id: 'text', icon: 'chatbox-outline', label: 'Text', color: BRAND.accent},
  {id: 'image', icon: 'image-outline', label: 'Image', color: '#4DA6FF'},
  {id: 'video', icon: 'videocam-outline', label: 'Video', color: '#C77DFF'},
  {id: 'camera', icon: 'camera-outline', label: 'Camera', color: '#FF6B8A'},
  {id: 'speech', icon: 'mic-outline', label: 'Speech', color: '#f97316'},
  {id: 'audio', icon: 'musical-note-outline', label: 'Audio', color: '#FFB84D'},
  {id: 'file', icon: 'document-outline', label: 'File', color: '#4DA6FF'},
  {id: 'url', icon: 'globe-outline', label: 'URL', color: '#FF6B8A'},
  {id: 'myfiles', icon: 'folder-open-outline', label: 'My Files', color: '#00D4AA'},
];

export const FILE_TYPE_STYLES: Record<string, {bg: string; color: string; label: string}> = {
  pdf: {bg: '#FF4B6E18', color: '#FF4B6E', label: 'PDF'},
  csv: {bg: '#00D4AA18', color: '#00D4AA', label: 'CSV'},
  pptx: {bg: '#C77DFF18', color: '#C77DFF', label: 'PPTX'},
  md: {bg: '#4DA6FF18', color: '#4DA6FF', label: 'MD'},
  docx: {bg: '#4DA6FF18', color: '#4DA6FF', label: 'DOCX'},
};
