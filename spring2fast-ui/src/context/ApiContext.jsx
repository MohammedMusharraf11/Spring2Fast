import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const ApiContext = createContext();

export const useApi = () => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApi must be used within ApiProvider');
  }
  return context;
};

export const ApiProvider = ({ children }) => {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000');
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const savedUrl = localStorage.getItem('apiUrl');
    if (savedUrl) {
      setApiUrl(savedUrl);
    }
  }, []);

  const checkConnection = useCallback(async () => {
    setChecking(true);
    try {
      await axios.get(`${apiUrl}/api/v1/health`, { timeout: 3000 });
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      setChecking(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 15000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  const updateApiUrl = (url) => {
    setApiUrl(url);
    localStorage.setItem('apiUrl', url);
  };

  /** Helper: build a full API url for a given path */
  const url = useCallback((path) => `${apiUrl}${path}`, [apiUrl]);

  /** Helper: GET request with base url */
  const get = useCallback(
    (path, config) => axios.get(url(path), config),
    [url]
  );

  /** Helper: POST request with base url */
  const post = useCallback(
    (path, data, config) => axios.post(url(path), data, config),
    [url]
  );

  return (
    <ApiContext.Provider
      value={{ apiUrl, updateApiUrl, connected, checking, checkConnection, url, get, post }}
    >
      {children}
    </ApiContext.Provider>
  );
};
