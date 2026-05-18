import React, { useState, useRef, useEffect } from 'react';
import { Upload, Send, FileText, Loader2, Image as ImageIcon, CheckCircle2, AlertCircle } from 'lucide-react';
import { uploadDocument, askQuestion, getDocuments, type DocumentItem } from './api';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  imageBase64?: string;
  sourcePage?: number;
};

function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isThinking, setIsThinking] = useState(false);

  const activeDocument = documents.find(doc => doc.id === activeDocId);
  const processingCount = documents.filter(doc => doc.status === 'processing').length;
  const isQueueFull = processingCount >= 3;
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, documents]);

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    const hasProcessingDocs = documents.some(doc => doc.status === 'processing');
    if (!hasProcessingDocs) return;

    const interval = setInterval(() => {
      fetchDocuments();
    }, 1500);

    return () => clearInterval(interval);
  }, [documents]);

  useEffect(() => {
    setMessages([]);
  }, [activeDocId]);

  const fetchDocuments = async () => {
    try {
      const docs = await getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error("Ошибка загрузки списка:", error);
    }
  };

  const handleUpload = async () => {
    if (!file || isQueueFull) return;

    setIsUploading(true); 
    
    try {
      const res = await uploadDocument(file);

      setFile(null); 

      await fetchDocuments(); 

      setActiveDocId(res.document_id);

    } catch (error) {
      console.error("Ошибка при загрузке файла", error);
      alert("Ошибка при загрузке файла.");
    } finally {
      setIsUploading(false); 
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !activeDocId || isThinking) return;

    const userMsg: Message = { id: Date.now().toString(), role: 'user', text: inputMessage };
    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setIsThinking(true);

    try {
      const res = await askQuestion(activeDocId, userMsg.text);
      setMessages(prev => [...prev, { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        text: res.answer,
        imageBase64: res.source_image_base64,
        sourcePage: res.source_page
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        id: (Date.now() + 1).toString(), 
        role: 'assistant', 
        text: 'Произошла ошибка при получении ответа от сервера.' 
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  const renderStatus = (doc: DocumentItem) => {
    if (doc.status === 'processing') return <Loader2 className="animate-spin text-blue-500" size={16} />;
    if (doc.status === 'completed') return <CheckCircle2 className="text-green-500" size={16} />;
    return <AlertCircle className="text-red-500" size={16} />;
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden font-sans">

      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-5 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
            <FileText className="text-blue-600" /> Мои документы
          </h2>
        </div>

       <div className="p-4 border-b border-gray-100 bg-gray-50">
          <div className="flex flex-col gap-2">
            <input 
              type="file" 
              accept=".pdf" 
              className="text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={isUploading || isQueueFull} 
            />
            <button
              onClick={handleUpload}
              disabled={!file || isUploading || isQueueFull}
              className="w-full bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 transition disabled:bg-blue-300 flex justify-center items-center gap-2"
            >
              {isUploading ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
              {isUploading ? 'Отправка...' : isQueueFull ? 'Очередь заполнена' : 'Загрузить PDF'}
            </button>
            
            {isQueueFull && (
              <p className="text-xs text-orange-500 text-center mt-1 font-medium">
                Сервер занят. Подождите немного.
              </p>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          {documents.length === 0 ? (
            <p className="text-sm text-gray-500 text-center mt-4">Нет загруженных документов</p>
          ) : (
            <div className="flex flex-col gap-2">
              {documents.map(doc => (
                <div 
                  key={doc.id}
                  onClick={() => setActiveDocId(doc.id)}
                  className={`p-3 rounded-xl border cursor-pointer transition flex items-start gap-3
                    ${activeDocId === doc.id ? 'bg-blue-50 border-blue-200' : 'bg-white border-gray-100 hover:border-blue-100'}
                  `}
                >
                  <div className="mt-1">{renderStatus(doc)}</div>
                  <div className="flex-1 overflow-hidden">
                    <p className="text-sm font-medium text-gray-800 truncate" title={doc.filename}>{doc.filename}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {doc.status === 'processing' 
                        ? `Обработка: ${doc.processed_pages} / ${doc.total_pages || '...'}` 
                        : new Date(doc.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col relative">
        {!activeDocument ? (
          <div className="flex-1 flex items-center justify-center flex-col text-gray-400">
            <ImageIcon size={64} className="mb-4 opacity-20" />
            <h2 className="text-xl font-medium text-gray-600">Выберите документ для работы</h2>
            <p className="text-sm mt-2">Загрузите новый PDF слева или выберите из истории</p>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 md:p-8">
              <div className="max-w-3xl mx-auto flex flex-col gap-6">

                {activeDocument.status === 'processing' ? (
                   <div className="flex justify-center mt-10">
                   <div className="bg-white border border-blue-100 rounded-2xl p-8 text-center shadow-sm w-full max-w-md">
                     <Loader2 className="animate-spin text-blue-500 mx-auto mb-4" size={32} />
                     <h3 className="text-lg font-medium text-gray-800 mb-2">Анализ документа</h3>
                     <p className="text-gray-500 text-sm mb-4">Нейросеть читает страницы и извлекает графики...</p>
                     
                     <div className="w-full bg-blue-100 rounded-full h-2">
                       <div 
                         className="bg-blue-600 h-2 rounded-full transition-all duration-500" 
                         style={{ width: `${Math.max(5, (activeDocument.processed_pages / Math.max(1, activeDocument.total_pages)) * 100)}%` }}
                       ></div>
                     </div>
                     <p className="text-xs mt-3 text-gray-400 font-medium">
                       Обработано {activeDocument.processed_pages} из {activeDocument.total_pages || '?'} страниц
                     </p>
                   </div>
                 </div>
                ) : activeDocument.status === 'error' ? (
                  <div className="bg-red-50 text-red-600 p-4 rounded-xl text-center mt-10">
                    Критическая ошибка при обработке файла: {activeDocument.error_message}
                  </div>
                ) : (
                  <>
                    {messages.length === 0 && (
                      <div className="text-center text-gray-400 mt-10">
                        <p>Документ "{activeDocument.filename}" готов к работе.</p>
                        <p className="text-sm">Задайте вопрос по тексту или графикам.</p>
                      </div>
                    )}
                    {messages.map((msg) => (
                      <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-2xl p-5 ${
                          msg.role === 'user' 
                            ? 'bg-blue-600 text-white rounded-br-none' 
                            : 'bg-white shadow-sm border border-gray-100 rounded-bl-none text-gray-800'
                        }`}>
                          <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>

                          {msg.imageBase64 && (
                            <div className="mt-4 pt-4 border-t border-gray-100">
                              <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wider">
                                Источник: Страница {msg.sourcePage}
                              </p>
                              <img 
                                src={`data:image/png;base64,${msg.imageBase64}`} 
                                alt={`Страница ${msg.sourcePage}`}
                                className="rounded-lg border border-gray-200 w-full object-contain bg-gray-50"
                                style={{ maxHeight: '400px' }}
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {isThinking && (
                  <div className="flex justify-start">
                    <div className="bg-white shadow-sm border border-gray-100 rounded-2xl rounded-bl-none p-5 flex items-center gap-3 text-gray-500">
                      <Loader2 className="animate-spin text-blue-600" size={20} />
                      <span>VLM анализирует контекст...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="bg-white border-t border-gray-200 p-4">
              <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex gap-3">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled={activeDocument?.status !== 'completed' || isThinking}
                  placeholder={
                    activeDocument?.status === 'processing' ? "Дождитесь окончания обработки..." : 
                    activeDocument?.status === 'error' ? "Работа с документом невозможна" :
                    "Спросите что-нибудь о документе..."
                  }
                  className="flex-1 bg-gray-50 border border-gray-300 rounded-xl px-5 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                />
                <button
                  type="submit"
                  disabled={!inputMessage.trim() || activeDocument?.status !== 'completed' || isThinking}
                  className="bg-blue-600 text-white rounded-xl px-5 py-3 hover:bg-blue-700 transition disabled:bg-blue-300 flex items-center justify-center disabled:cursor-not-allowed"
                >
                  <Send size={20} />
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;