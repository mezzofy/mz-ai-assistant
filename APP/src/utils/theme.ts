export const BRAND = {
  primary: '#0A1628',
  secondary: '#1B2B44',
  accent: '#00D4AA',
  accentGlow: 'rgba(0,212,170,0.15)',
  accentSoft: '#00D4AA22',
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

export const INPUT_MODES = [
  {id: 'text', icon: 'chatbox-outline', label: 'Text', color: BRAND.accent},
  {id: 'image', icon: 'image-outline', label: 'Image', color: '#4DA6FF'},
  {id: 'video', icon: 'videocam-outline', label: 'Video', color: '#C77DFF'},
  {id: 'camera', icon: 'camera-outline', label: 'Camera', color: '#FF6B8A'},
  {id: 'speech', icon: 'mic-outline', label: 'Speech', color: '#00D4AA'},
  {id: 'audio', icon: 'musical-note-outline', label: 'Audio', color: '#FFB84D'},
  {id: 'file', icon: 'document-outline', label: 'File', color: '#4DA6FF'},
  {id: 'url', icon: 'globe-outline', label: 'URL', color: '#FF6B8A'},
];

export const FILE_TYPE_STYLES: Record<string, {bg: string; color: string; label: string}> = {
  pdf: {bg: '#FF4B6E18', color: '#FF4B6E', label: 'PDF'},
  csv: {bg: '#00D4AA18', color: '#00D4AA', label: 'CSV'},
  pptx: {bg: '#C77DFF18', color: '#C77DFF', label: 'PPTX'},
  md: {bg: '#4DA6FF18', color: '#4DA6FF', label: 'MD'},
  docx: {bg: '#4DA6FF18', color: '#4DA6FF', label: 'DOCX'},
};

export const DEMO_USER = {
  name: 'Sarah Chen',
  email: 'sarah@mezzofy.com',
  department: 'sales',
  role: 'sales_rep',
  permissions: ['sales_read', 'sales_write', 'email_send', 'linkedin_access', 'calendar_access'],
};

export const DEMO_RESPONSES: Record<string, {text: string; artifacts: {type: string; name: string; size: string}[]; tools: string[]}> = {
  finance: {
    text: "I've generated the Q4 2025 Financial Statement. Revenue is up 23% YoY at $1.8M. The PDF has been emailed to CEO James Wong via Outlook.",
    artifacts: [{type: 'pdf', name: 'Financial_Statement_Q4_2025.pdf', size: '2.4 MB'}],
    tools: ['database_query', 'pdf_generator', 'outlook_send_email'],
  },
  sales: {
    text: 'Found 23 F&B companies in Singapore. Saved to CRM and sent personalized intro emails to 20 contacts via Outlook.',
    artifacts: [{type: 'csv', name: 'leads_singapore_fnb.csv', size: '48 KB'}],
    tools: ['linkedin_search', 'crm_save', 'outlook_batch_send'],
  },
  marketing: {
    text: "Here's the website copy and customer playbook for the new Loyalty 2.0 feature. Both use our latest brand guidelines.",
    artifacts: [
      {type: 'md', name: 'loyalty_website_copy.md', size: '12 KB'},
      {type: 'pdf', name: 'Loyalty_2.0_Playbook.pdf', size: '3.1 MB'},
    ],
    tools: ['knowledge_search', 'content_generator', 'pdf_generator'],
  },
  support: {
    text: 'This week: 47 tickets, 89% resolved within SLA. Recurring issue: 12 tickets about coupon redemption timeout.',
    artifacts: [{type: 'pdf', name: 'Support_Weekly_Report.pdf', size: '1.8 MB'}],
    tools: ['database_query', 'data_analysis', 'pdf_generator'],
  },
  management: {
    text: 'Cross-department KPI report ready. Sales pipeline at $420K (+18%), support SLA at 89%, LLM costs: $127 this month.',
    artifacts: [{type: 'pdf', name: 'KPI_Dashboard_Feb_2026.pdf', size: '2.7 MB'}],
    tools: ['query_all_departments', 'data_analysis', 'pdf_generator'],
  },
};
