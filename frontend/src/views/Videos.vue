<template>
  <div class="videos-page">
    <el-alert 
      v-if="!projectStore.hasProject" 
      title="请先选择项目" 
      type="warning" 
      show-icon 
      :closable="false"
    />
    
    <template v-else>
      <el-card class="box-card">
        <template #header>
          <div class="card-header">
            <span>视频生成</span>
            <div>
              <el-button @click="fetchData" :loading="loading">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </div>
        </template>

        <el-form :inline="true" :model="form" class="demo-form-inline">
          <el-form-item label="时长">
            <el-select v-model="form.duration" style="width: 100px">
              <el-option label="5s" value="5s" />
              <el-option label="10s" value="10s" />
            </el-select>
          </el-form-item>
          <el-form-item label="尺寸">
            <el-select v-model="form.size" style="width: 130px">
              <el-option label="竖屏 720x1280" value="720x1280" />
              <el-option label="横屏 1280x720" value="1280x720" />
            </el-select>
          </el-form-item>
          <el-form-item label="水印">
            <el-switch v-model="form.watermark" />
          </el-form-item>
          <el-form-item label="分镜范围">
            <el-input 
              v-model="form.shot_range" 
              placeholder="留空=全部"
              style="width: 200px"
            />
          </el-form-item>
          <el-form-item>
            <el-button 
              type="primary" 
              @click="generateVideos"
              :loading="generating"
            >
              生成视频
            </el-button>
          </el-form-item>
        </el-form>

        <el-alert 
          v-if="videos.length === 0" 
          title="暂无视频生成记录"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />

        <div class="video-grid">
          <div 
            v-for="video in videos" 
            :key="video.task_id"
            class="video-card"
          >
            <el-card :body-style="{ padding: '0px' }">
              <div class="video-wrapper">
                <video 
                  v-if="video.local_path" 
                  :src="getVideoUrl(video.local_path)" 
                  class="video-player"
                  controls
                />
                <div v-else-if="video.status === 'completed' && video.video_url" class="video-pending">
                  <el-icon :size="48" color="#409EFF"><VideoPlay /></el-icon>
                  <p>视频已生成，点击下载</p>
                  <el-button type="primary" size="small" @click="downloadVideo(video)">
                    下载视频
                  </el-button>
                </div>
                <div v-else-if="video.status === 'processing'" class="video-pending">
                  <el-progress :percentage="video.progress || 0" />
                  <p>生成中...</p>
                </div>
                <div v-else-if="video.status === 'submitted'" class="video-pending">
                  <el-icon :size="48" color="#909399"><Loading /></el-icon>
                  <p>等待处理...</p>
                </div>
                <div v-else-if="video.status === 'failed'" class="video-error">
                  <el-icon :size="48" color="#F56C6C"><CircleClose /></el-icon>
                  <p>生成失败</p>
                  <el-button type="warning" size="small" @click="checkStatus(video.shot_id)">
                    重试检查
                  </el-button>
                </div>
                <div v-else class="video-pending">
                  <el-icon :size="48" color="#909399"><VideoCamera /></el-icon>
                  <p>等待生成</p>
                </div>
              </div>
              <div class="video-info">
                <h4>{{ video.shot_id }}</h4>
                <p class="description">{{ video.prompt?.substring(0, 60) }}...</p>
                <div class="video-meta">
                  <el-tag :type="statusType(video.status)" size="small">
                    {{ video.status }}
                  </el-tag>
                  <span class="duration">{{ video.duration }}</span>
                  <span class="size">{{ video.size }}</span>
                </div>
                <div class="video-actions" v-if="video.status === 'completed'">
                  <el-button type="primary" size="small" @click="playVideo(video)">
                    播放
                  </el-button>
                  <el-button type="warning" size="small" @click="regenerateVideo(video)">
                    重新生成
                  </el-button>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </el-card>

      <!-- 视频播放对话框 -->
      <el-dialog v-model="playerDialog.visible" title="视频预览" width="800px">
        <video 
          v-if="playerDialog.videoUrl" 
          :src="playerDialog.videoUrl" 
          class="dialog-video"
          controls
          autoplay
        />
        <div v-else class="no-video">视频不可用</div>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { videoApi, shotApi } from '../api'
import { useProjectStore } from '../stores/project'

const projectStore = useProjectStore()
const videos = ref([])
const loading = ref(false)
const generating = ref(false)

const form = ref({
  duration: '5s',
  size: '1280x720',
  watermark: false,
  shot_range: ''
})

const playerDialog = ref({
  visible: false,
  videoUrl: ''
})

let timer = null

const statusType = (status) => {
  const map = {
    'submitted': 'info',
    'processing': 'warning',
    'completed': 'success',
    'failed': 'danger'
  }
  return map[status] || 'info'
}

const getVideoUrl = (path) => {
  if (!path) return ''
  // 将绝对路径转换为相对于 static 目录的路径
  const parts = path.split('animation_projects/')
  if (parts.length > 1) {
    return `http://localhost:8000/static/${parts[1]}`
  }
  return path
}

const fetchData = async () => {
  if (!projectStore.projectId) return
  loading.value = true
  try {
    const res = await videoApi.list(projectStore.projectId)
    videos.value = res.data || []
  } catch (e) {
    console.error('获取视频列表失败:', e)
  } finally {
    loading.value = false
  }
}

const generateVideos = async () => {
  if (!projectStore.projectId) return
  generating.value = true
  try {
    const shotIds = form.value.shot_range 
      ? form.value.shot_range.split(',').map(s => s.trim())
      : null
    
    await videoApi.generate(projectStore.projectId, {
      duration: form.value.duration,
      size: form.value.size,
      watermark: form.value.watermark,
      shot_ids: shotIds
    })
    ElMessage.success('视频生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

const checkStatus = async (shotId) => {
  if (!projectStore.projectId) return
  try {
    const res = await videoApi.checkStatus(projectStore.projectId, shotId)
    const videosData = res.data.videos || []
    
    // 更新本地数据
    videosData.forEach(newVideo => {
      const idx = videos.value.findIndex(v => v.task_id === newVideo.task_id)
      if (idx !== -1) {
        videos.value[idx] = { ...videos.value[idx], ...newVideo }
      }
    })
    
    ElMessage.success('状态已更新')
  } catch (e) {
    ElMessage.error('检查状态失败')
  }
}

const playVideo = (video) => {
  if (video.local_path) {
    playerDialog.value.videoUrl = getVideoUrl(video.local_path)
    playerDialog.value.visible = true
  } else if (video.video_url) {
    playerDialog.value.videoUrl = video.video_url
    playerDialog.value.visible = true
  } else {
    ElMessage.warning('视频暂不可用')
  }
}

const downloadVideo = (video) => {
  if (video.video_url) {
    window.open(video.video_url, '_blank')
  } else {
    ElMessage.warning('视频链接不可用')
  }
}

const regenerateVideo = async (video) => {
  // 重新生成视频 - 使用相同的参数
  try {
    await videoApi.generate(projectStore.projectId, {
      shot_ids: [video.shot_id],
      duration: video.duration,
      size: video.size,
      watermark: false
    })
    ElMessage.success('重新生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  }
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 10000) // 10秒刷新一次
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

.demo-form-inline {
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.video-card {
  break-inside: avoid;
}

.video-wrapper {
  height: 200px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-pending {
  text-align: center;
  color: #909399;
}

.video-pending p {
  margin: 10px 0;
}

.video-error {
  text-align: center;
  color: #F56C6C;
}

.video-error p {
  margin: 10px 0;
}

.video-info {
  padding: 14px;
}

.video-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.video-info .description {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #666;
  height: 40px;
  overflow: hidden;
}

.video-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12px;
  color: #909399;
}

.video-actions {
  display: flex;
  gap: 10px;
}

.dialog-video {
  width: 100%;
  max-height: 600px;
}

.no-video {
  text-align: center;
  padding: 40px;
  color: #909399;
}
</style>
