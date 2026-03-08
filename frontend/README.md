# 前端 Vue 项目

## 启动
```bash
cd frontend
npm install
npm run dev
```

## 访问
- 首页：`http://127.0.0.1:5173`
- 输入股票代码跳转 `/stock/:code`

## 后端接口
前端通过 `/api` 代理访问后端：
```
/api/stocks/{code}/history?start=YYYY-MM-DD&end=YYYY-MM-DD
```
