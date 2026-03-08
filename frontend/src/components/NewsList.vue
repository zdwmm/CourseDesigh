<template>
  <div class="news-wrap">
    <h3>相关新闻</h3>
    <p v-if="loading">加载中...</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="news.length === 0">暂无新闻数据</p>
    <ul v-else>
      <li v-for="(item, idx) in news" :key="idx" class="news-item">
        <div class="title">{{ item.title }}</div>
        <div class="meta">
          <span>{{ item.published_at }}</span>
          <span> · {{ item.source || "unknown" }}</span>
        </div>
        <div class="summary">{{ item.summary || "" }}</div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { fetchNews } from "../services/api";

const props = defineProps({
  code: { type: String, required: true },
  limit: { type: Number, default: 20 },
});

const news = ref([]);
const loading = ref(false);
const error = ref("");

const loadNews = async () => {
  loading.value = true;
  error.value = "";
  try {
    news.value = await fetchNews(props.code, props.limit);
  } catch (e) {
    error.value = e?.response?.data?.detail || "新闻加载失败";
    news.value = [];
  } finally {
    loading.value = false;
  }
};

watch(() => props.code, loadNews, { immediate: true });
</script>

<style scoped>
.news-wrap { margin-top: 20px; }
.news-item { padding: 10px 0; border-bottom: 1px solid #eee; }
.title { font-weight: 600; }
.meta { color: #888; font-size: 12px; margin: 4px 0; }
.summary { color: #333; }
.error { color: red; }
</style>