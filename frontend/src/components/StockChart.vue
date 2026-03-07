<template>
  <div>
    <div ref="chartRef" class="chart"></div>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import * as echarts from "echarts";
import { fetchHistory } from "../services/api";

const props = defineProps({
  code: String,
  days: Number
});

const chartRef = ref(null);
const chart = ref(null);
const error = ref("");

const loadData = async () => {
  error.value = "";
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - props.days + 1);

  const format = (d) => d.toISOString().slice(0, 10);

  try {
    const data = await fetchHistory(props.code, format(start), format(end));
    const dates = data.map((d) => d.date);
    const values = data.map((d) => d.close);

    if (!chart.value) {
      chart.value = echarts.init(chartRef.value);
    }

    chart.value.setOption({
      title: { text: "收盘价折线图" },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: dates },
      yAxis: { type: "value" },
      series: [
        {
          name: "Close",
          type: "line",
          data: values,
          smooth: true
        }
      ]
    });
  } catch (e) {
    error.value = e?.response?.data?.detail || "加载数据失败";
  }
};

watch(() => [props.code, props.days], loadData, { immediate: true });

onMounted(() => {
  if (!chart.value && chartRef.value) {
    chart.value = echarts.init(chartRef.value);
  }
});
</script>

<style scoped>
.chart {
  width: 100%;
  height: 400px;
}
.error {
  color: red;
  margin-top: 8px;
}
</style>
