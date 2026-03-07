# 后端 FastAPI PoC

## 快速启动（本地）

1. 安装依赖

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 启动服务

```
uvicorn app.main:app --reload
```

3. 测试示例

```
curl http://127.0.0.1:8000/health
curl -X POST "http://127.0.0.1:8000/admin/fetch_prices/AAPL?period_days=365"
curl -X POST "http://127.0.0.1:8000/admin/import_news/AAPL"
curl -X POST "http://127.0.0.1:8000/admin/sentiment/AAPL"
curl "http://127.0.0.1:8000/prediction/AAPL?window=30&alpha=0.01"
```

---

## 历史行情 API（第3天）

接口：
```
GET /stocks/{code}/history?start=YYYY-MM-DD&end=YYYY-MM-DD
```

示例：
```
curl "http://127.0.0.1:8000/stocks/AAPL/history?start=2023-01-01&end=2023-12-31"
```

参数说明：
- `start` / `end` 必须为 `YYYY-MM-DD` 格式
- 当 `start > end` 时返回 400
- 当无数据时返回 404
