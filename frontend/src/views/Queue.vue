<template>
  <div class="queue-page">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>队列状态</span>
          <el-button @click="fetchStatus" :loading="loading">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8" v-for="(stats, name) in queues" :key="name">
          <el-card class="queue-card" :body-style="{ padding: '20px' }">
            <div class="queue-title">
              <el-icon size="24" color="#409EFF"><Histogram /></el-icon>
              <span>{{ name.toUpperCase() }} 队列</span>
            </div>
            <div class="queue-stats">
              <div class="stat-item">
                <div class="stat-value pending">{{ stats.pending }}</div>
                <div class="stat-label">待处理</div>
              </div>
              <div class="stat-item">
                <div class="stat-value running">{{ stats.running }}</div>
                <div class="stat-label">运行中</div>
              </div>
              <div class="stat-item">
                <div class="stat-value completed">{{ stats.completed }}</div>
                <div class="stat-label">已完成</div>
              </div>
              <div class="stat-item">
                <div class="stat-value failed">{{ stats.failed }}</div>
                <div class="stat-label">失败</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-divider />

      <div class="queue-info">
        <h3>队列说明</h3>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="LLM 队列">
            处理剧本解析、分镜设计等文本生成任务
          </el-descriptions-item>
          <el-descriptions-item label="Image 队列">
            处理参考图、首帧生成等图片生成任务
          </el-descriptions-item>
          <el-descriptions-item label="Video 队列">
            处理视频生成任务
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { queueApi } from '../api'

const queues = ref({
  llm: { pending: 0, running: 0, completed: 0, failed: 0 },
  image: { pending: 0, running: 0, completed: 0, failed: 0 },
  video: { pending: 0, running: 0, completed: 0, failed: 0 }
})
const loading = ref(false)
let timer = null

const fetchStatus = async () => {
  loading.value = true
  try {
    const res = await queueApi.status()
    queues.value = res.data
  } catch (e) {
    console.error('获取队列状态失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStatus()
  timer = setInterval(fetchStatus, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.queue-card {
  text-align: center;
}

.queue-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 20px;
  font-size: 18px;
  font-weight: 600;
}

.queue-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 5px;
}

.stat-value.pending { color: #e6a23c; }
.stat-value.running { color: #409eff; }
.stat-value.completed { color: #67c23a; }
.stat-value.failed { color: #f56c6c; }

.stat-label {
  font-size: 12px;
  color: #909399;
}

.queue-info {
  margin-top: 20px;
}

.queue-info h3 {
  margin-bottom: 15px;
}
</style>
