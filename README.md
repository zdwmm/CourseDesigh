# CourseDesigh

## 项目启动（后端）

进入后端目录并安装依赖：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

---

## Docker 一键启动（后端）

```bash
docker compose up --build
```

---

## 环境变量

- `NEWSAPI_KEY`：可选，NewsAPI 调用密钥  
- `DATABASE_URL`：默认 `sqlite:///./data.db`  

---

## 示例流程

```bash
curl -X POST "http://127.0.0.1:8000/admin/fetch_prices/AAPL?period_days=365"
curl -X POST "http://127.0.0.1:8000/admin/import_news/AAPL"
curl -X POST "http://127.0.0.1:8000/admin/sentiment/AAPL"
curl "http://127.0.0.1:8000/prediction/AAPL?window=30&alpha=0.01"
```
