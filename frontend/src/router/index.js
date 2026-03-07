import { createRouter, createWebHistory } from "vue-router";
import Home from "../views/Home.vue";
import StockDetail from "../views/StockDetail.vue";

const routes = [
  { path: "/", component: Home },
  { path: "/stock/:code", component: StockDetail }
];

export default createRouter({
  history: createWebHistory(),
  routes
});
