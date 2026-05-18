import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
});

export interface DocumentItem {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'error';
  uploaded_at: string;
  total_pages: number;
  processed_pages: number;
  error_message?: string;
}

export interface UploadResponse {
  document_id: string;
  message?: string;
}

export interface ChatResponse {
  answer: string;
  source_page: number;
  source_image_base64: string;
}

export const getDocuments = async (): Promise<DocumentItem[]> => {
  const response = await apiClient.get('/documents');
  return response.data;
};

export const getDocumentStatus = async (documentId: string): Promise<DocumentItem> => {
  const response = await apiClient.get(`/documents/${documentId}/status`);
  return response.data;
};

export const uploadDocument = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post('/documents/upload', formData);
  return response.data;
};

export const askQuestion = async (documentId: string, question: string): Promise<ChatResponse> => {
  const response = await apiClient.post('/chat/ask', {
    document_id: documentId,
    question: question,
  });
  return response.data;
};