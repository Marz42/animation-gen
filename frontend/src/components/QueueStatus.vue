<template>
  <div class="queue-status">
    <el-tag type="info" size="small" @click="fetchStatus" style="cursor: pointer;">
      <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
      <span v-else>
        LLM: {{ status?.llm?.pending || 0 }} | 
        IMG: {{ status?.image?.pending || 0 }} | 
        VID: {{ status?.video?.pending || 0 }}
      </span>
    </el-tag>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { queueApi } from '../api'

const status = ref(null)
const loading = ref(false)
let timer = null

const fetchStatus = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const res = await queueApi.status()
    status.value = res.data
  } catch (e) {
    console.error('获取队列状态失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStatus()
  // 30秒自动刷新一次，减少干扰
  timer = setInterval(fetchStatus, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.queue-status {
  display: flex;
  align-items: center;
}
</style>
