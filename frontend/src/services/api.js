import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

//export async function fetchHistory(code, start, end) {
//  const res = await axios.get(`/api/stocks/${code}/history`, {
//    params: { start, end }
//  });
//  return res.data;
//}

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