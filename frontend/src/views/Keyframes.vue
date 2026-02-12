<template>
  <div class="keyframes-page">
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
            <span>首帧生成</span>
            <div>
              <el-button @click="estimateCost" :loading="estimating">
                成本预估
              </el-button>
              <el-button 
                type="primary" 
                @click="generateKeyframes"
                :loading="generating"
              >
                生成所有首帧
              </el-button>
              <el-button @click="fetchData" :loading="loading">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
              <el-button type="info" @click="showPromptDialog = true">
                <el-icon><Setting /></el-icon>编辑提示词
              </el-button>
            </div>
          </div>
        </template>

        <el-alert 
          v-if="costEstimate" 
          :title="costText"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />

        <div class="image-grid">
          <div 
            v-for="shot in shotsWithKeyframes" 
            :key="shot.shot_id"
            class="image-card"
          >
            <el-card :body-style="{ padding: '0px' }">
              <div class="image-wrapper" @click="showShotDetail(shot)">
                <img 
                  v-if="getKeyframeImage(shot)" 
                  :src="getKeyframeImage(shot)" 
                  class="keyframe-image"
                />
                <div v-else class="no-image">暂无首帧</div>
              </div>
              <div class="image-info">
                <h4>{{ shot.shot_id }}</h4>
                <p class="description">{{ shot.description?.substring(0, 50) }}...</p>
                <div class="shot-actions">
                  <el-tag :type="getKeyframeStatusType(shot)" size="small">
                    {{ getKeyframeStatus(shot) || '待生成' }}
                  </el-tag>
                  <el-button 
                    v-if="getKeyframeImage(shot)" 
                    type="primary" 
                    size="small"
                    @click="showRegenerateDialog(shot)"
                  >
                    重新生成
                  </el-button>
                </div>
              </div>
            </el-card>
          </div>
        </div>
      </el-card>

      <!-- 分镜详情对话框 -->
      <el-dialog v-model="detailDialog.visible" :title="detailDialog.shot?.shot_id" width="700px">
        <div v-if="detailDialog.shot" class="shot-detail">
          <div class="detail-image">
            <img 
              v-if="getKeyframeImage(detailDialog.shot)" 
              :src="getKeyframeImage(detailDialog.shot)" 
              class="detail-img"
            />
            <div v-else class="no-detail-image">暂无首帧</div>
          </div>

          <el-divider>提示词</el-divider>
          
          <div class="prompt-section" v-if="!detailDialog.editing">
            <div class="prompt-block">
              <div class="prompt-label">正面提示词</div>
              <div class="prompt-content">{{ detailDialog.shot.image_prompt?.positive || '未生成' }}</div>
            </div>
            <div class="prompt-block">
              <div class="prompt-label">负面提示词</div>
              <div class="prompt-content">{{ detailDialog.shot.image_prompt?.negative || '未生成' }}</div>
            </div>
            <div class="prompt-actions">
              <el-button type="primary" @click="startEditPrompt">
                <el-icon><Edit /></el-icon>编辑Prompt
              </el-button>
              <el-button type="warning" @click="showRegenerateFromDetail">
                <el-icon><Refresh /></el-icon>重新生成
              </el-button>
            </div>
          </div>

          <div class="prompt-edit" v-else>
            <el-form label-position="top">
              <el-form-item label="正面提示词">
                <el-input 
                  v-model="detailDialog.editForm.positive" 
                  type="textarea" 
                  :rows="4"
                />
              </el-form-item>
              <el-form-item label="负面提示词">
                <el-input 
                  v-model="detailDialog.editForm.negative" 
                  type="textarea" 
                  :rows="2"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="savePrompt" :loading="detailDialog.saving">
                  保存
                </el-button>
                <el-button @click="detailDialog.editing = false">取消</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-dialog>

      <!-- 重新生成对话框 -->
      <el-dialog v-model="regenerateDialog.visible" title="重新生成首帧" width="500px">
        <el-form label-width="100px">
          <el-form-item label="生成方式">
            <el-radio-group v-model="regenerateForm.method">
              <el-radio label="seed">更换Seed</el-radio>
              <el-radio label="prompt">修改Prompt</el-radio>
              <el-radio label="both">两者都改</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="新Seed" v-if="regenerateForm.method === 'seed' || regenerateForm.method === 'both'">
            <el-input-number v-model="regenerateForm.new_seed" :min="0" :max="999999999" />
          </el-form-item>
          <el-form-item label="新提示词" v-if="regenerateForm.method === 'prompt' || regenerateForm.method === 'both'">
            <el-input 
              v-model="regenerateForm.new_prompt" 
              type="textarea" 
              :rows="4"
              placeholder="输入新的提示词..."
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="regenerateDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="confirmRegenerate" :loading="regenerateForm.loading">
            重新生成
          </el-button>
        </template>
      </el-dialog>

      <!-- 编辑首帧生成提示词对话框 -->
      <el-dialog v-model="showPromptDialog" title="编辑首帧生成提示词" width="800px">
        <el-alert
          title="修改提示词后，下次生成首帧时将使用新提示词。此提示词与分镜设计页面的提示词是独立的。"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-alert
          title="此提示词用于指导LLM生成每个分镜的图片/视频提示词。系统会自动将分镜信息（描述、角色、场景等）传递给LLM。"
          type="warning"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-tabs v-model="promptActiveTab">
          <el-tab-pane label="图片提示词 (image_prompt)" name="image">
            <el-form label-position="top">
              <el-form-item>
                <template #label>
                  <span>图片生成提示词模板</span>
                  <el-tooltip placement="top">
                    <template #content>
                      <div style="max-width: 350px;">
                        <b>此模板用于指导LLM生成每个分镜的图片提示词</b><br/><br/>
                        <b>可用占位符变量：</b><br/>
                        [[SHOT_DESCRIPTION]] - 分镜描述<br/>
                        [[CHARACTERS]] - 涉及角色及其描述<br/>
                        [[SCENE_REF]] - 场景描述<br/>
                        [[STYLE]] - 整体风格描述<br/><br/>
                        <b>LLM应返回JSON格式：</b><br/>
                        {&quot;positive&quot;: &quot;...&quot;, &quot;negative&quot;: &quot;...&quot;}
                      </div>
                    </template>
                    <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
                <el-input 
                  v-model="promptForm.image_prompt" 
                  type="textarea" 
                  :rows="15"
                  placeholder="输入图片生成提示词模板...&#10;&#10;可用占位符变量:&#10;[[SHOT_DESCRIPTION]] - 分镜描述&#10;[[CHARACTERS]] - 涉及角色及其描述&#10;[[SCENE_REF]] - 场景描述&#10;[[STYLE]] - 整体风格描述&#10;&#10;LLM应返回JSON格式: {&quot;positive&quot;: &quot;...&quot;, &quot;negative&quot;: &quot;...&quot;}&#10;&#10;提示: 使用双括号格式 [[VARIABLE]] 来插入变量"
                />
              </el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="视频提示词 (video_prompt)" name="video">
            <el-form label-position="top">
              <el-form-item>
                <template #label>
                  <span>视频生成提示词模板</span>
                  <el-tooltip placement="top">
                    <template #content>
                      <div style="max-width: 350px;">
                        <b>此模板用于指导LLM生成每个分镜的视频提示词</b><br/><br/>
                        <b>可用占位符变量：</b><br/>
                        [[SCENE_DESCRIPTION]] - 剧本场景描述<br/>
                        [[IMAGE_PROMPT]] - 首帧图片提示词<br/>
                        [[CHARACTERS]] - 角色信息<br/>
                        [[ACTION]] - 分镜动作描述<br/>
                        [[CAMERA_MOVEMENT]] - 镜头运动<br/>
                        [[DURATION]] - 持续时间<br/><br/>
                        <b>LLM应返回：</b>视频描述文本
                      </div>
                    </template>
                    <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
                <el-input 
                  v-model="promptForm.video_prompt" 
                  type="textarea" 
                  :rows="15"
                  placeholder="输入视频生成提示词模板...&#10;&#10;可用占位符变量:&#10;[[SCENE_DESCRIPTION]] - 剧本场景描述&#10;[[IMAGE_PROMPT]] - 首帧图片提示词&#10;[[CHARACTERS]] - 角色信息&#10;[[ACTION]] - 分镜动作描述&#10;[[CAMERA_MOVEMENT]] - 镜头运动&#10;[[DURATION]] - 持续时间&#10;&#10;LLM应返回视频描述文本。&#10;&#10;提示: 使用双括号格式 [[VARIABLE]] 来插入变量"
                />
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <template #footer>
          <el-button @click="showPromptDialog = false">取消</el-button>
          <el-button type="primary" @click="savePromptConfig" :loading="promptForm.saving">
            保存
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled, Refresh, Setting, Edit } from '@element-plus/icons-vue'
import { shotApi, keyframeApi, promptApi } from '../api'
import { useProjectStore } from '../stores/project'

const projectStore = useProjectStore()
const shots = ref([])
const loading = ref(false)
const generating = ref(false)
const estimating = ref(false)
const costEstimate = ref(null)
let timer = null

// 详情对话框
const detailDialog = ref({
  visible: false,
  shot: null,
  editing: false,
  saving: false,
  editForm: {
    positive: '',
    negative: ''
  }
})

// 重新生成对话框
const regenerateDialog = ref({
  visible: false,
  shot: null
})

const regenerateForm = ref({
  method: 'seed',
  new_seed: Math.floor(Math.random() * 1000000),
  new_prompt: '',
  loading: false
})

// 提示词编辑对话框
const showPromptDialog = ref(false)
const promptActiveTab = ref('image')
const promptForm = ref({
  image_prompt: '',
  video_prompt: '',
  saving: false
})

const shotsWithKeyframes = computed(() => {
  return shots.value.filter(s => s.batches && Object.keys(s.batches).length > 0)
})

const costText = computed(() => {
  if (!costEstimate.value) return ''
  const { shot_count, total_seconds, estimated_cost_usd } = costEstimate.value
  return `分镜数: ${shot_count} | 总时长: ${total_seconds}s | 预估成本: $${estimated_cost_usd}`
})

const getImageUrl = (path) => {
  if (!path) return ''
  const parts = path.split('animation_projects/')
  if (parts.length > 1) {
    return `http://localhost:8000/static/${parts[1]}`
  }
  return path
}

const getKeyframeImage = (shot) => {
  const batchId = shot.current_batch_id
  if (!batchId || !shot.batches[batchId]) return null
  const path = shot.batches[batchId].keyframe?.path
  return getImageUrl(path)
}

const getKeyframeStatus = (shot) => {
  const batchId = shot.current_batch_id
  if (!batchId || !shot.batches[batchId]) return null
  return shot.batches[batchId].keyframe?.status
}

const getKeyframeStatusType = (shot) => {
  const status = getKeyframeStatus(shot)
  const map = {
    'completed': 'success',
    'pending_review': 'warning',
    'approved': 'success',
    'failed': 'danger'
  }
  return map[status] || 'info'
}

const fetchData = async () => {
  if (!projectStore.projectId) return
  loading.value = true
  try {
    const res = await shotApi.list(projectStore.projectId)
    shots.value = res.data
  } catch (e) {
    console.error('获取分镜失败:', e)
  } finally {
    loading.value = false
  }
}

const estimateCost = async () => {
  if (!projectStore.projectId) return
  estimating.value = true
  try {
    const res = await keyframeApi.estimateCost(projectStore.projectId)
    costEstimate.value = res.data
  } catch (e) {
    ElMessage.error('获取成本预估失败')
  } finally {
    estimating.value = false
  }
}

const generateKeyframes = async () => {
  if (!projectStore.projectId) return
  generating.value = true
  try {
    await keyframeApi.generate(projectStore.projectId)
    ElMessage.success('首帧生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

// 显示分镜详情
const showShotDetail = (shot) => {
  detailDialog.value.shot = shot
  detailDialog.value.editing = false
  detailDialog.value.visible = true
}

// 开始编辑 Prompt
const startEditPrompt = () => {
  const shot = detailDialog.value.shot
  detailDialog.value.editForm = {
    positive: shot.image_prompt?.positive || '',
    negative: shot.image_prompt?.negative || ''
  }
  detailDialog.value.editing = true
}

// 保存 Prompt
const savePrompt = async () => {
  detailDialog.value.saving = true
  try {
    await keyframeApi.editPrompt(projectStore.projectId, detailDialog.value.shot.shot_id, {
      positive_prompt: detailDialog.value.editForm.positive,
      negative_prompt: detailDialog.value.editForm.negative
    })
    
    // 更新本地数据
    if (!detailDialog.value.shot.image_prompt) {
      detailDialog.value.shot.image_prompt = {}
    }
    detailDialog.value.shot.image_prompt.positive = detailDialog.value.editForm.positive
    detailDialog.value.shot.image_prompt.negative = detailDialog.value.editForm.negative
    detailDialog.value.editing = false
    
    ElMessage.success('提示词已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    detailDialog.value.saving = false
  }
}

// 显示重新生成对话框
const showRegenerateDialog = (shot) => {
  regenerateDialog.value.shot = shot
  regenerateForm.value.new_prompt = shot.image_prompt?.positive || ''
  regenerateForm.value.new_seed = Math.floor(Math.random() * 1000000)
  regenerateDialog.value.visible = true
}

// 从详情页显示重新生成
const showRegenerateFromDetail = () => {
  regenerateDialog.value.shot = detailDialog.value.shot
  regenerateForm.value.new_prompt = detailDialog.value.shot.image_prompt?.positive || ''
  regenerateForm.value.new_seed = Math.floor(Math.random() * 1000000)
  regenerateDialog.value.visible = true
}

// 确认重新生成
const confirmRegenerate = async () => {
  regenerateForm.value.loading = true
  try {
    await keyframeApi.regenerate(projectStore.projectId, regenerateDialog.value.shot.shot_id, {
      method: regenerateForm.value.method,
      new_seed: regenerateForm.value.method !== 'prompt' ? regenerateForm.value.new_seed : undefined,
      new_prompt: regenerateForm.value.method !== 'seed' ? regenerateForm.value.new_prompt : undefined
    })
    
    regenerateDialog.value.visible = false
    detailDialog.value.visible = false
    ElMessage.success('重新生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    regenerateForm.value.loading = false
  }
}

// 加载提示词配置
const loadPromptConfig = async () => {
  try {
    const res = await promptApi.get()
    promptForm.value.image_prompt = res.data.image_prompt || ''
    promptForm.value.video_prompt = res.data.video_prompt || ''
  } catch (e) {
    console.error('加载提示词配置失败:', e)
  }
}

// 保存提示词配置
const savePromptConfig = async () => {
  promptForm.value.saving = true
  try {
    await promptApi.update({
      image_prompt: promptForm.value.image_prompt,
      video_prompt: promptForm.value.video_prompt
    })
    ElMessage.success('提示词配置已保存')
    showPromptDialog.value = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    promptForm.value.saving = false
  }
}

onMounted(() => {
  fetchData()
  loadPromptConfig()
  timer = setInterval(fetchData, 5000)
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

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.image-card {
  break-inside: avoid;
}

.image-wrapper {
  height: 180px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
}

.keyframe-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-image {
  color: #999;
}

.image-info {
  padding: 14px;
}

.image-info h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.image-info .description {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #666;
}

.shot-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

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

.prompt-section {
  margin: 20px 0;
}

.prompt-block {
  margin-bottom: 15px;
}

.prompt-label {
  font-weight: bold;
  color: #606266;
  margin-bottom: 5px;
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

.prompt-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

.prompt-edit {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}
</style>
