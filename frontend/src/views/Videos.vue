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
              <el-button @click="showVideoPromptTemplateDialog" type="info">
                <el-icon><Setting /></el-icon>编辑视频Prompt模板
              </el-button>
              <el-button @click="fetchData" :loading="loading">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </div>
        </template>

        <!-- 批量操作栏 -->
        <div class="batch-actions" v-if="selectedShots.length > 0">
          <el-alert
            :title="`已选择 ${selectedShots.length} 个分镜`"
            type="info"
            :closable="false"
            show-icon
          >
            <template #default>
              <div class="batch-buttons">
                <el-button type="primary" size="small" @click="generateVideoPromptsForSelected" :loading="generatingPrompt === 'batch'">
                  生成视频Prompt
                </el-button>
                <el-button type="info" size="small" @click="regenerateVideoPromptsForSelected" :loading="regeneratingPrompt === 'batch'">
                  重新生成
                </el-button>
                <el-button type="success" size="small" @click="generateVideosForSelected">
                  生成视频
                </el-button>
                <el-button 
                  type="warning" 
                  size="small" 
                  @click="batchDownload"
                  :disabled="completedSelectedCount === 0"
                  :loading="downloading"
                >
                  <el-icon><Download /></el-icon>
                  批量下载 ({{ completedSelectedCount }})
                </el-button>
                <el-button size="small" @click="clearSelection">取消选择</el-button>
              </div>
            </template>
          </el-alert>
        </div>

        <!-- 全选操作栏 -->
        <div class="select-all-bar" v-else-if="videos.length > 0">
          <el-button type="primary" link @click="selectAll">
            <el-icon><Select /></el-icon> 全选 ({{ videos.length }}个)
          </el-button>
          <el-button type="info" link @click="selectAllWithPrompt">
            选择有Prompt的 ({{ videos.filter(v => v.video_prompt).length }}个)
          </el-button>
          <el-button type="info" link @click="selectAllWithoutPrompt">
            选择无Prompt的 ({{ videos.filter(v => !v.video_prompt).length }}个)
          </el-button>
        </div>

        <!-- 生成参数设置 -->
        <el-form :inline="true" :model="form" class="demo-form-inline">
          <el-form-item label="提供商">
            <el-select v-model="form.provider" style="width: 160px" :disabled="selectedShots.length === 0 && videos.length > 0">
              <el-option-group label="内置提供商">
                <el-option 
                  v-for="p in availableProviders.filter(p => p.type === 'builtin')" 
                  :key="p.id" 
                  :label="p.name" 
                  :value="p.id" 
                />
              </el-option-group>
              <el-option-group label="自定义提供商" v-if="customProviders.length > 0">
                <el-option 
                  v-for="p in customProviders" 
                  :key="p.id" 
                  :label="p.name" 
                  :value="p.id" 
                />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="时长">
            <el-select v-model="form.duration" style="width: 100px">
              <el-option 
                v-for="d in currentProviderConfig?.durations || ['4s', '8s', '12s']" 
                :key="d" 
                :label="d" 
                :value="d" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="尺寸">
            <el-select v-model="form.size" style="width: 130px">
              <el-option 
                v-for="s in currentProviderConfig?.resolutions || ['720p', '1080p']" 
                :key="s" 
                :label="s" 
                :value="s" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="水印">
            <el-switch v-model="form.watermark" />
          </el-form-item>
          <el-form-item>
            <el-button 
              type="primary" 
              @click="generateAllVideos"
              :loading="generating"
              :disabled="selectedShots.length > 0"
            >
              生成所有视频
            </el-button>
          </el-form-item>
        </el-form>

        <el-alert 
          v-if="videos.length === 0" 
          title="暂无可生成的分镜，请先在首帧生成页面完成首帧"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />

        <!-- 分镜网格 -->
        <div class="video-grid">
          <div 
            v-for="video in videos" 
            :key="video.shot_id"
            class="video-card"
            :class="{ 'is-selected': isSelected(video.shot_id) }"
          >
            <el-card :body-style="{ padding: '0px' }">
              <!-- 选择框 -->
              <div class="selection-overlay" @click.stop="toggleSelection(video.shot_id)">
                <el-checkbox :model-value="isSelected(video.shot_id)" size="large" />
              </div>
              
              <!-- 视频预览区域 -->
              <div class="media-wrapper" @click="showVideoDetail(video)">
                <!-- 视频已完成：显示视频播放器 -->
                <template v-if="video.status === 'completed' && (video.local_path || video.video_url)">
                  <video 
                    :src="getVideoUrl(video)" 
                    class="video-player-preview"
                    preload="metadata"
                    muted
                    playsinline
                  />
                  <div class="video-play-overlay">
                    <el-icon :size="48" color="#fff"><VideoPlay /></el-icon>
                  </div>
                </template>
                
                <!-- 其他状态：显示首帧图片 -->
                <template v-else>
                  <img 
                    v-if="video.keyframe_path" 
                    :src="getImageUrl(video.keyframe_path)" 
                    class="keyframe-image"
                  />
                  <div v-else class="no-keyframe">暂无首帧</div>
                </template>
                
                <!-- 视频状态覆盖层 -->
                <div class="video-status-overlay" :class="getVideoStatus(video)">
                  <el-tag :type="getVideoStatusType(video)" effect="dark" size="small">
                    {{ getVideoStatusText(video) }}
                  </el-tag>
                  <span v-if="video.status === 'completed'" class="video-duration">{{ video.duration }}</span>
                </div>
                
                <!-- 进度条 -->
                <div class="progress-overlay" v-if="video.status === 'processing'">
                  <el-progress :percentage="video.progress || 0" :stroke-width="4" />
                </div>
              </div>
              
              <!-- 信息区域 -->
              <div class="video-info">
                <div class="info-header">
                  <h4>{{ video.shot_id }}</h4>
                  <el-tag size="small" :type="shotStatusType(video.status)">
                    {{ shotStatusText(video.status) }}
                  </el-tag>
                </div>
                
                <!-- Prompt信息 -->
                <div class="prompt-info">
                  <div class="prompt-section">
                    <div class="prompt-label">
                      首帧Prompt
                      <el-button 
                        link 
                        type="primary" 
                        size="small"
                        @click="editImagePrompt(video)"
                      >
                        编辑
                      </el-button>
                    </div>
                    <div class="prompt-text" :title="video.image_prompt?.positive">
                      {{ video.image_prompt?.positive?.substring(0, 50) || '未设置' }}...
                    </div>
                  </div>
                  
                  <div class="prompt-section">
                    <div class="prompt-label">
                      视频Prompt
                      <el-button 
                        v-if="!video.video_prompt"
                        link 
                        type="success" 
                        size="small"
                        @click="generateVideoPrompt(video)"
                        :loading="generatingPrompt === video.shot_id"
                      >
                        生成
                      </el-button>
                      <el-button 
                        v-else
                        link 
                        type="primary" 
                        size="small"
                        @click="editVideoPrompt(video)"
                      >
                        编辑
                      </el-button>
                    </div>
                    <div class="prompt-text" :title="video.video_prompt?.description">
                      {{ video.video_prompt?.description?.substring(0, 50) || '未生成' }}...
                    </div>
                  </div>
                </div>
                
                <!-- 操作按钮 -->
                <div class="video-actions">
                  <!-- 生成按钮 -->
                  <el-button 
                    v-if="video.status !== 'completed' && video.status !== 'video_generating' && video.keyframe_path && video.video_prompt"
                    type="primary" 
                    size="small"
                    @click="generateSingleVideo(video)"
                    :loading="generating === video.shot_id"
                  >
                    生成视频
                  </el-button>
                  
                  <!-- 播放按钮 -->
                  <el-button 
                    v-if="video.status === 'completed'"
                    type="success" 
                    size="small"
                    @click="playVideo(video)"
                    :disabled="!getVideoUrl(video)"
                  >
                    <el-icon><VideoPlay /></el-icon> 播放
                  </el-button>
                  
                  <!-- 下载按钮 -->
                  <el-button 
                    v-if="video.status === 'completed'"
                    size="small"
                    @click="downloadVideo(video)"
                    :disabled="!getVideoUrl(video)"
                  >
                    <el-icon><Download /></el-icon> 下载
                  </el-button>
                  
                  <!-- 重新生成按钮 -->
                  <el-button 
                    v-if="video.status === 'completed' || video.status === 'failed'"
                    type="warning"
                    size="small"
                    @click="regenerateVideo(video)"
                  >
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

      <!-- 首帧Prompt编辑对话框 -->
      <el-dialog v-model="imagePromptDialog.visible" title="编辑首帧Prompt" width="600px">
        <el-form label-position="top" v-if="imagePromptDialog.video">
          <el-form-item label="正面提示词">
            <el-input 
              v-model="imagePromptDialog.form.positive" 
              type="textarea" 
              :rows="4"
            />
          </el-form-item>
          <el-form-item label="负面提示词">
            <el-input 
              v-model="imagePromptDialog.form.negative" 
              type="textarea" 
              :rows="2"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="imagePromptDialog.visible = false">取消</el-button>
          <el-button type="warning" @click="saveImagePromptAndRegenerate" :loading="imagePromptDialog.regenerating">
            保存并重新生成首帧
          </el-button>
          <el-button type="primary" @click="saveImagePromptOnly" :loading="imagePromptDialog.saving">
            仅保存
          </el-button>
        </template>
      </el-dialog>

      <!-- 视频Prompt编辑对话框 -->
      <el-dialog v-model="videoPromptDialog.visible" title="视频Prompt" width="600px">
        <el-form label-position="top" v-if="videoPromptDialog.video">
          <el-form-item label="视频描述">
            <el-input 
              v-model="videoPromptDialog.form.description" 
              type="textarea" 
              :rows="6"
              placeholder="描述视频画面主体动作、相机运动、光影变化..."
            />
          </el-form-item>
          <el-form-item label="相机运动">
            <el-input v-model="videoPromptDialog.form.camera" placeholder="例如：static, pan_left, zoom_in..." />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="videoPromptDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="saveVideoPrompt" :loading="videoPromptDialog.saving">
            保存
          </el-button>
        </template>
      </el-dialog>

      <!-- 视频Prompt模板编辑对话框 -->
      <el-dialog v-model="promptTemplateDialog.visible" title="编辑视频Prompt生成模板" width="800px">
        <el-alert
          title="此模板用于指导LLM生成视频Prompt。系统会自动替换以下占位符："
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-descriptions :column="2" border size="small" style="margin-bottom: 15px;">
          <el-descriptions-item label="[[SCENE_DESCRIPTION]]">剧本场景描述</el-descriptions-item>
          <el-descriptions-item label="[[IMAGE_PROMPT]]">首帧图片提示词</el-descriptions-item>
          <el-descriptions-item label="[[CHARACTERS]]">角色信息</el-descriptions-item>
          <el-descriptions-item label="[[ACTION]]">分镜动作描述</el-descriptions-item>
          <el-descriptions-item label="[[CAMERA_MOVEMENT]]">镜头运动</el-descriptions-item>
          <el-descriptions-item label="[[DURATION]]">持续时间</el-descriptions-item>
        </el-descriptions>
        <el-input 
          v-model="promptTemplateDialog.template" 
          type="textarea" 
          :rows="15"
          placeholder="输入视频Prompt生成模板..."
        />
        <template #footer>
          <el-button @click="promptTemplateDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="saveVideoPromptTemplate" :loading="promptTemplateDialog.saving">
            保存模板
          </el-button>
        </template>
      </el-dialog>

      <!-- 分镜详情对话框 -->
      <el-dialog v-model="detailDialog.visible" :title="detailDialog.video?.shot_id" width="700px">
        <div v-if="detailDialog.video" class="shot-detail">
          <div class="detail-image">
            <img 
              v-if="detailDialog.video.keyframe_path" 
              :src="getImageUrl(detailDialog.video.keyframe_path)" 
              class="detail-img"
            />
            <div v-else class="no-detail-image">暂无首帧</div>
          </div>

          <el-tabs v-model="detailDialog.activeTab">
            <el-tab-pane label="首帧Prompt" name="image">
              <div class="prompt-block">
                <div class="prompt-label">正面提示词</div>
                <div class="prompt-content">{{ detailDialog.video.image_prompt?.positive || '未设置' }}</div>
              </div>
              <div class="prompt-block">
                <div class="prompt-label">负面提示词</div>
                <div class="prompt-content">{{ detailDialog.video.image_prompt?.negative || '未设置' }}</div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="视频Prompt" name="video">
              <div class="prompt-block">
                <div class="prompt-label">视频描述</div>
                <div class="prompt-content">{{ detailDialog.video.video_prompt?.description || '未生成' }}</div>
              </div>
              <div class="prompt-block">
                <div class="prompt-label">相机运动</div>
                <div class="prompt-content">{{ detailDialog.video.video_prompt?.camera || '未设置' }}</div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="视频信息" name="info" v-if="detailDialog.video.task_id">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="任务ID">{{ detailDialog.video.task_id }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ detailDialog.video.status }}</el-descriptions-item>
                <el-descriptions-item label="时长">{{ detailDialog.video.duration }}</el-descriptions-item>
                <el-descriptions-item label="尺寸">{{ detailDialog.video.size }}</el-descriptions-item>
                <el-descriptions-item label="提供商">{{ detailDialog.video.provider }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ detailDialog.video.created_at }}</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Setting, VideoPlay, Download, Select } from '@element-plus/icons-vue'
import { videoApi, promptApi, shotApi } from '../api'
import { useProjectStore } from '../stores/project'

const projectStore = useProjectStore()
const videos = ref([])
const loading = ref(false)
const generating = ref(false)
const generatingPrompt = ref(null)
const regeneratingPrompt = ref(null)
const selectedShots = ref([])
const downloading = ref(false)

// 提供商配置
const providerConfig = ref(null)
const availableProviders = ref([])
const customProviders = ref([])
const currentProviderConfig = ref(null)

const form = ref({
  provider: 'jiekouai',
  duration: '4s',
  size: '720p',
  watermark: false
})

// 计算已选中的已完成视频数量
const completedSelectedCount = computed(() => {
  return videos.value.filter(v => 
    selectedShots.value.includes(v.shot_id) && v.status === 'completed'
  ).length
})

// 加载提供商配置
const loadProviderConfig = async () => {
  try {
    const res = await videoApi.getProviderConfig()
    providerConfig.value = res.data.current_config
    availableProviders.value = res.data.available_providers || []
    customProviders.value = res.data.custom_providers || []
    
    // 设置默认提供商
    if (res.data.current_provider) {
      form.value.provider = res.data.current_provider
    }
    
    // 设置当前提供商配置
    currentProviderConfig.value = providerConfig.value
    
    // 设置默认值
    if (providerConfig.value) {
      form.value.duration = providerConfig.value.default_duration || '4s'
      form.value.size = providerConfig.value.default_resolution || '720p'
    }
  } catch (e) {
    console.error('加载提供商配置失败:', e)
  }
}

// 对话框状态
const playerDialog = ref({
  visible: false,
  videoUrl: ''
})

const imagePromptDialog = ref({
  visible: false,
  video: null,
  saving: false,
  regenerating: false,
  form: {
    positive: '',
    negative: ''
  }
})

const videoPromptDialog = ref({
  visible: false,
  video: null,
  saving: false,
  form: {
    description: '',
    camera: ''
  }
})

const promptTemplateDialog = ref({
  visible: false,
  saving: false,
  template: ''
})

const detailDialog = ref({
  visible: false,
  video: null,
  activeTab: 'image'
})

let timer = null

// 工具函数
const getImageUrl = (path) => {
  if (!path) return ''
  const parts = path.split('animation_projects/')
  if (parts.length > 1) {
    return `http://localhost:8000/static/${parts[1]}`
  }
  return path
}

const getVideoUrl = (video) => {
  // 优先使用本地路径
  if (video.local_path) {
    const parts = video.local_path.split('animation_projects/')
    if (parts.length > 1) {
      return `http://localhost:8000/static/${parts[1]}`
    }
  }
  // 否则使用远程 URL
  if (video.video_url) {
    return video.video_url
  }
  return ''
}

const getVideoStatus = (video) => {
  if (video.status === 'completed') return 'completed'
  if (video.status === 'video_generating') return video.progress > 0 ? 'processing' : 'submitted'
  if (video.task_id) return video.status
  return 'pending'
}

const getVideoStatusType = (video) => {
  const status = getVideoStatus(video)
  const map = {
    'completed': 'success',
    'processing': 'warning',
    'submitted': 'info',
    'failed': 'danger',
    'pending': 'info'
  }
  return map[status] || 'info'
}

const getVideoStatusText = (video) => {
  const status = getVideoStatus(video)
  const map = {
    'completed': '已完成',
    'processing': '生成中',
    'submitted': '已提交',
    'failed': '失败',
    'pending': '待生成'
  }
  return map[status] || status
}

const shotStatusType = (status) => {
  const map = {
    'frame_approved': 'success',
    'frame_pending_review': 'warning',
    'video_generating': 'primary',
    'completed': 'success',
    'failed': 'danger'
  }
  return map[status] || 'info'
}

const shotStatusText = (status) => {
  const map = {
    'frame_approved': '首帧已审核',
    'frame_pending_review': '首帧待审核',
    'video_generating': '视频生成中',
    'completed': '已完成',
    'failed': '失败'
  }
  return map[status] || status
}

// 选择相关
const isSelected = (shotId) => selectedShots.value.includes(shotId)

const toggleSelection = (shotId) => {
  const idx = selectedShots.value.indexOf(shotId)
  if (idx > -1) {
    selectedShots.value.splice(idx, 1)
  } else {
    selectedShots.value.push(shotId)
  }
}

const clearSelection = () => {
  selectedShots.value = []
}

const selectAll = () => {
  selectedShots.value = videos.value.map(v => v.shot_id)
  ElMessage.success(`已选择 ${selectedShots.value.length} 个分镜`)
}

const selectAllWithPrompt = () => {
  selectedShots.value = videos.value.filter(v => v.video_prompt).map(v => v.shot_id)
  ElMessage.success(`已选择 ${selectedShots.value.length} 个有Prompt的分镜`)
}

const selectAllWithoutPrompt = () => {
  selectedShots.value = videos.value.filter(v => !v.video_prompt).map(v => v.shot_id)
  ElMessage.success(`已选择 ${selectedShots.value.length} 个无Prompt的分镜`)
}

// 数据获取
const fetchData = async () => {
  if (!projectStore.projectId) return
  loading.value = true
  try {
    const res = await videoApi.list(projectStore.projectId)
    videos.value = res.data || []
  } catch (e) {
    console.error('获取视频列表失败:', e)
    ElMessage.error('获取视频列表失败')
  } finally {
    loading.value = false
  }
}

// 视频生成
const generateSingleVideo = async (video) => {
  if (!video.video_prompt) {
    ElMessage.warning('请先生成视频Prompt')
    return
  }
  
  generating.value = video.shot_id
  try {
    await videoApi.generate(projectStore.projectId, {
      shot_ids: [video.shot_id],
      duration: form.value.duration,
      size: form.value.size,
      watermark: form.value.watermark,
      provider: form.value.provider
    })
    ElMessage.success('视频生成任务已提交')
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

const generateAllVideos = async () => {
  generating.value = true
  try {
    await videoApi.generate(projectStore.projectId, {
      duration: form.value.duration,
      size: form.value.size,
      watermark: form.value.watermark,
      provider: form.value.provider
    })
    ElMessage.success('视频生成任务已提交')
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

const generateVideosForSelected = async () => {
  if (selectedShots.value.length === 0) {
    ElMessage.warning('请先选择分镜')
    return
  }
  
  // 检查是否都有视频Prompt
  const selectedVideos = videos.value.filter(v => selectedShots.value.includes(v.shot_id))
  const missingPrompt = selectedVideos.filter(v => !v.video_prompt)
  if (missingPrompt.length > 0) {
    ElMessage.warning(`${missingPrompt.map(v => v.shot_id).join(', ')} 缺少视频Prompt，请先生成`)
    return
  }
  
  generating.value = true
  try {
    await videoApi.generate(projectStore.projectId, {
      shot_ids: selectedShots.value,
      duration: form.value.duration,
      size: form.value.size,
      watermark: form.value.watermark,
      provider: form.value.provider
    })
    ElMessage.success('视频生成任务已提交')
    clearSelection()
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

// 批量下载
const batchDownload = async () => {
  if (selectedShots.value.length === 0) {
    ElMessage.warning('请先选择分镜')
    return
  }
  
  downloading.value = true
  try {
    const res = await videoApi.batchDownload(projectStore.projectId, {
      shot_ids: selectedShots.value
    })
    
    const downloads = res.data.downloads || []
    if (downloads.length === 0) {
      ElMessage.warning('选中的分镜中没有可下载的已完成视频')
      return
    }
    
    // 依次下载每个视频
    let successCount = 0
    for (const item of downloads) {
      try {
        const link = document.createElement('a')
        link.href = item.url
        link.download = item.filename
        link.target = '_blank'
        link.click()
        successCount++
        // 添加小延迟避免浏览器阻塞
        await new Promise(resolve => setTimeout(resolve, 500))
      } catch (e) {
        console.error(`下载 ${item.shot_id} 失败:`, e)
      }
    }
    
    ElMessage.success(`已开始下载 ${successCount} 个视频`)
  } catch (e) {
    ElMessage.error('批量下载失败')
  } finally {
    downloading.value = false
  }
}

// 首帧Prompt编辑
const editImagePrompt = (video) => {
  imagePromptDialog.value.video = video
  imagePromptDialog.value.form = {
    positive: video.image_prompt?.positive || '',
    negative: video.image_prompt?.negative || ''
  }
  imagePromptDialog.value.visible = true
}

const saveImagePromptOnly = async () => {
  imagePromptDialog.value.saving = true
  try {
    // 调用首帧编辑API保存
    await shotApi.editPrompt(projectStore.projectId, imagePromptDialog.value.video.shot_id, {
      positive_prompt: imagePromptDialog.value.form.positive,
      negative_prompt: imagePromptDialog.value.form.negative
    })
    
    // 更新本地数据
    if (!imagePromptDialog.value.video.image_prompt) {
      imagePromptDialog.value.video.image_prompt = {}
    }
    imagePromptDialog.value.video.image_prompt.positive = imagePromptDialog.value.form.positive
    imagePromptDialog.value.video.image_prompt.negative = imagePromptDialog.value.form.negative
    
    ElMessage.success('首帧Prompt已保存')
    imagePromptDialog.value.visible = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    imagePromptDialog.value.saving = false
  }
}

const saveImagePromptAndRegenerate = async () => {
  // 确认对话框
  try {
    await ElMessageBox.confirm(
      '重新生成首帧会重置该分镜的视频状态，已生成的视频将被清除。是否继续？',
      '警告',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  
  imagePromptDialog.value.regenerating = true
  try {
    await videoApi.regenerateKeyframe(projectStore.projectId, imagePromptDialog.value.video.shot_id, {
      positive_prompt: imagePromptDialog.value.form.positive,
      negative_prompt: imagePromptDialog.value.form.negative
    })
    
    ElMessage.success('首帧重新生成任务已提交，视频状态已重置')
    imagePromptDialog.value.visible = false
    fetchData()
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    imagePromptDialog.value.regenerating = false
  }
}

// 视频Prompt生成和编辑
const generateVideoPrompt = async (video) => {
  generatingPrompt.value = video.shot_id
  try {
    const res = await videoApi.generateVideoPrompt(projectStore.projectId, video.shot_id, {
      use_template: true
    })
    
    // 更新本地数据
    video.video_prompt = res.data.video_prompt
    ElMessage.success('视频Prompt生成成功')
  } catch (e) {
    ElMessage.error('生成失败')
  } finally {
    generatingPrompt.value = null
  }
}

const editVideoPrompt = (video) => {
  videoPromptDialog.value.video = video
  videoPromptDialog.value.form = {
    description: video.video_prompt?.description || '',
    camera: video.video_prompt?.camera || ''
  }
  videoPromptDialog.value.visible = true
}

const saveVideoPrompt = async () => {
  videoPromptDialog.value.saving = true
  try {
    await videoApi.saveVideoPrompt(projectStore.projectId, videoPromptDialog.value.video.shot_id, {
      description: videoPromptDialog.value.form.description,
      camera: videoPromptDialog.value.form.camera
    })
    
    // 更新本地数据
    videoPromptDialog.value.video.video_prompt = {
      description: videoPromptDialog.value.form.description,
      camera: videoPromptDialog.value.form.camera
    }
    
    ElMessage.success('视频Prompt已保存')
    videoPromptDialog.value.visible = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    videoPromptDialog.value.saving = false
  }
}

// 为选中的分镜生成视频Prompt（只生成没有的）
const generateVideoPromptsForSelected = async () => {
  if (selectedShots.value.length === 0) {
    ElMessage.warning('请先选择分镜')
    return
  }
  
  // 统计没有Prompt的分镜
  const missingPromptShots = selectedShots.value.filter(shotId => {
    const video = videos.value.find(v => v.shot_id === shotId)
    return video && !video.video_prompt
  })
  
  if (missingPromptShots.length === 0) {
    ElMessage.info('选中的分镜都已存在视频Prompt，如需重新生成请使用"重新生成"按钮')
    return
  }
  
  generatingPrompt.value = 'batch'
  let successCount = 0
  let failCount = 0
  
  try {
    for (const shotId of missingPromptShots) {
      try {
        await videoApi.generateVideoPrompt(projectStore.projectId, shotId, { use_template: true })
        successCount++
      } catch (e) {
        console.error(`生成 ${shotId} 的Prompt失败:`, e)
        failCount++
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`成功生成 ${successCount} 个视频Prompt`)
    }
    if (failCount > 0) {
      ElMessage.warning(`${failCount} 个生成失败`)
    }
    
    fetchData()
  } catch (e) {
    ElMessage.error('生成过程出错')
  } finally {
    generatingPrompt.value = null
  }
}

// 重新生成选中的分镜的视频Prompt（覆盖已有）
const regenerateVideoPromptsForSelected = async () => {
  if (selectedShots.value.length === 0) {
    ElMessage.warning('请先选择分镜')
    return
  }
  
  // 确认对话框
  try {
    await ElMessageBox.confirm(
      `确定要重新生成 ${selectedShots.value.length} 个分镜的视频Prompt吗？这将覆盖已有的Prompt。`,
      '确认重新生成',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  
  regeneratingPrompt.value = 'batch'
  let successCount = 0
  let failCount = 0
  
  try {
    for (const shotId of selectedShots.value) {
      try {
        await videoApi.generateVideoPrompt(projectStore.projectId, shotId, { use_template: true })
        successCount++
      } catch (e) {
        console.error(`重新生成 ${shotId} 的Prompt失败:`, e)
        failCount++
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`成功重新生成 ${successCount} 个视频Prompt`)
    }
    if (failCount > 0) {
      ElMessage.warning(`${failCount} 个重新生成失败`)
    }
    
    fetchData()
  } catch (e) {
    ElMessage.error('重新生成过程出错')
  } finally {
    regeneratingPrompt.value = null
  }
}

// 视频Prompt模板
const showVideoPromptTemplateDialog = async () => {
  try {
    const res = await promptApi.get()
    promptTemplateDialog.value.template = res.data.video_prompt || ''
    promptTemplateDialog.value.visible = true
  } catch (e) {
    ElMessage.error('加载模板失败')
  }
}

const saveVideoPromptTemplate = async () => {
  promptTemplateDialog.value.saving = true
  try {
    await promptApi.update({
      video_prompt: promptTemplateDialog.value.template
    })
    ElMessage.success('模板已保存')
    promptTemplateDialog.value.visible = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    promptTemplateDialog.value.saving = false
  }
}

// 视频播放和下载
const playVideo = (video) => {
  const url = getVideoUrl(video)
  if (url) {
    playerDialog.value.videoUrl = url
    playerDialog.value.visible = true
  } else {
    ElMessage.warning('视频暂不可用')
  }
}

const downloadVideo = (video) => {
  const url = getVideoUrl(video)
  if (url) {
    // 创建一个临时链接来下载
    const link = document.createElement('a')
    link.href = url
    link.download = `${video.shot_id}.mp4`
    link.target = '_blank'
    link.click()
  } else {
    ElMessage.warning('视频链接不可用')
  }
}

// 重新生成视频
const regenerateVideo = async (video) => {
  try {
    await ElMessageBox.confirm(
      '确定要重新生成这个视频吗？之前的视频将被替换。',
      '确认重新生成',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    
    generating.value = video.shot_id
    await videoApi.generate(projectStore.projectId, {
      shot_ids: [video.shot_id],
      duration: form.value.duration,
      size: form.value.size,
      watermark: form.value.watermark
    })
    ElMessage.success('重新生成任务已提交')
    fetchData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('提交失败')
    }
  } finally {
    generating.value = false
  }
}

// 详情查看
const showVideoDetail = (video) => {
  detailDialog.value.video = video
  detailDialog.value.activeTab = 'image'
  detailDialog.value.visible = true
}

onMounted(() => {
  loadProviderConfig()
  fetchData()
  timer = setInterval(fetchData, 10000)
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

.batch-actions {
  margin-bottom: 20px;
}

.batch-buttons {
  display: flex;
  gap: 10px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.select-all-bar {
  margin-bottom: 20px;
  padding: 10px 15px;
  background: #f5f7fa;
  border-radius: 4px;
  display: flex;
  gap: 15px;
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
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

.video-card {
  break-inside: avoid;
  position: relative;
}

.video-card.is-selected {
  outline: 2px solid #409EFF;
  outline-offset: 2px;
}

.selection-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 4px;
  padding: 4px;
  cursor: pointer;
}

.media-wrapper {
  height: 200px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
  cursor: pointer;
}

.keyframe-wrapper {
  height: 200px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
  cursor: pointer;
}

.keyframe-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-player-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-play-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  transition: opacity 0.3s;
}

.media-wrapper:hover .video-play-overlay {
  opacity: 1;
}

.no-keyframe {
  color: #999;
  font-size: 14px;
}

.video-status-overlay {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
}

.video-status-overlay.completed {
  top: auto;
  bottom: 10px;
}

.video-duration {
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.progress-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 10px;
  background: rgba(0, 0, 0, 0.5);
}

.video-info {
  padding: 14px;
}

.info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.info-header h4 {
  margin: 0;
  font-size: 16px;
}

.prompt-info {
  margin-bottom: 10px;
}

.prompt-section {
  margin-bottom: 8px;
}

.prompt-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.prompt-text {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: #f5f7fa;
  padding: 6px 8px;
  border-radius: 4px;
}

.video-actions {
  display: flex;
  gap: 8px;
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

/* 详情对话框样式 */
.shot-detail {
  max-height: 600px;
  overflow-y: auto;
}

.detail-image {
  text-align: center;
  margin-bottom: 20px;
}

.detail-img {
  max-width: 100%;
  max-height: 300px;
  object-fit: contain;
}

.no-detail-image {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #999;
}

.prompt-block {
  margin-bottom: 15px;
}

.prompt-content {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
