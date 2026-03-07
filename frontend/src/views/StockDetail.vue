<template>
  <div>
    <h2>股票：{{ code }}</h2>
    <div class="controls">
      <button @click="setWindow(30)">1M</button>
      <button @click="setWindow(90)">3M</button>
      <button @click="setWindow(180)">6M</button>
    </div>
    <StockChart :code="code" :days="days" />
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { useRoute } from "vue-router";
import StockChart from "../components/StockChart.vue";

const route = useRoute();
const code = computed(() => route.params.code.toString().toUpperCase());
const days = ref(30);

const setWindow = (d) => {
  days.value = d;
};
</script>

<style scoped>
.controls {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
button {
  padding: 6px 12px;
}
</style>
