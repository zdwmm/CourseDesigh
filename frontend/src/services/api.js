import axios from "axios";

export async function fetchHistory(code, start, end) {
  const res = await axios.get(`/api/stocks/${code}/history`, {
    params: { start, end }
  });
  return res.data;
}
