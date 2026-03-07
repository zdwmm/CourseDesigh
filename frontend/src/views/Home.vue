<template>
  <div class="home">
    <h2>输入股票代码</h2>
    <input v-model="code" placeholder="例如 AAPL" />
    <button @click="go">查看</button>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const code = ref("AAPL");
const router = useRouter();

const go = () => {
  if (!code.value.trim()) return;
  router.push(`/stock/${code.value.trim().toUpperCase()}`);
};
</script>

<style scoped>
.home {
  display: flex;
  gap: 8px;
  align-items: center;
}
input {
  padding: 6px;
}
button {
  padding: 6px 12px;
}
</style>
