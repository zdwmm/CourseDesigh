import axios from "axios";

const api = axios.create({
  // 开发环境走 Vite 代理，生产可在 .env 中设置 VITE_API_BASE_URL 指向后端网关
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

export const fetchHistory = async (code, start, end) => {
  const { data } = await api.get(`/stocks/${code}/history`, {
    params: { start, end },
  });
  return data;
};

export const fetchNews = async (code, limit = 20) => {
  const { data } = await api.get(`/news/${code}`, {
    params: { limit },
  });
  return data;
};