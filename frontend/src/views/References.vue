<template>
  <div class="references-page">
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
            <span>参考图生成</span>
            <div>
              <el-button 
                type="primary" 
                @click="generateReferences"
                :loading="generating"
              >
                生成所有参考图
              </el-button>
              <el-button @click="fetchData" :loading="loading">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
              <el-button type="info" @click="showPromptDialog = true">
                编辑提示词
              </el-button>
            </div>
          </div>
        </template>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="角色参考图" name="characters">
            <div class="image-grid">
              <div 
                v-for="char in characters" 
                :key="char.character_id"
                class="image-card"
              >
                <el-card :body-style="{ padding: '0px' }">
                  <div class="image-wrapper">
                    <img 
                      v-if="getCurrentImage(char)" 
                      :src="getImageUrl(getCurrentImage(char))" 
                      class="reference-image"
                      @error="handleImageError"
                    />
                    <div v-else class="no-image">暂无图片</div>
                  </div>
                  <div class="image-info">
                    <h4>{{ char.name }}</h4>
                    <p class="description">{{ char.description?.substring(0, 50) }}...</p>
                    <div class="prompt-preview" v-if="getCurrentVersion(char)?.prompt">
                      <div class="prompt-text">{{ getCurrentVersion(char).prompt.substring(0, 60) }}...</div>
                    </div>
                    <div class="actions">
                      <el-tag :type="getCurrentVersion(char)?.status === 'approved' ? 'success' : 'info'" size="small">
                        {{ getCurrentVersion(char)?.status || '待生成' }}
                      </el-tag>
                      <el-dropdown size="small" split-button type="primary" @click="regenerateCharacter(char)">
                        重新生成
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item @click="openRegenerateDialog(char, 'character')">
                              高级选项
                            </el-dropdown-item>
                            <el-dropdown-item @click="openEditPromptDialog(char, 'character')">
                              编辑Prompt
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>
                </el-card>
              </div>
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="场景参考图" name="scenes">
            <div class="image-grid">
              <div 
                v-for="scene in scenes" 
                :key="scene.scene_id"
                class="image-card"
              >
                <el-card :body-style="{ padding: '0px' }">
                  <div class="image-wrapper">
                    <img 
                      v-if="getCurrentImage(scene)" 
                      :src="getImageUrl(getCurrentImage(scene))" 
                      class="reference-image"
                      @error="handleImageError"
                    />
                    <div v-else class="no-image">暂无图片</div>
                  </div>
                  <div class="image-info">
                    <h4>{{ scene.name }}</h4>
                    <p class="location">{{ scene.location }} | {{ scene.time }}</p>
                    <div class="prompt-preview" v-if="getCurrentVersion(scene)?.prompt">
                      <div class="prompt-text">{{ getCurrentVersion(scene).prompt.substring(0, 60) }}...</div>
                    </div>
                    <div class="actions">
                      <el-tag :type="getCurrentVersion(scene)?.status === 'approved' ? 'success' : 'info'" size="small">
                        {{ getCurrentVersion(scene)?.status || '待生成' }}
                      </el-tag>
                      <el-dropdown size="small" split-button type="primary" @click="regenerateScene(scene)">
                        重新生成
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item @click="openRegenerateDialog(scene, 'scene')">
                              高级选项
                            </el-dropdown-item>
                            <el-dropdown-item @click="openEditPromptDialog(scene, 'scene')">
                              编辑Prompt
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </div>
                </el-card>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <!-- 提示词编辑对话框 -->
      <el-dialog v-model="showPromptDialog" title="编辑参考图提示词" width="800px">
        <el-alert
          title="提示词中可使用以下变量占位符来引用前阶段解析的角色/场景信息"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-form :model="prompts" label-width="120px">
          <el-form-item>
            <template #label>
              <span>角色提示词模板</span>
              <el-tooltip placement="top">
                <template #content>
                  可用变量：<br/>
                  [[NAME]] - 角色名称<br/>
                  [[DESCRIPTION]] - 角色外貌描述<br/>
                  [[PERSONALITY]] - 角色性格<br/>
                  [[STYLE]] - 项目风格描述
                </template>
                <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
            <el-input 
              v-model="prompts.character_ref_prompt" 
              type="textarea" 
              :rows="8"
              placeholder="编辑角色参考图生成的提示词模板...&#10;&#10;可用变量:&#10;[[NAME]] - 角色名称&#10;[[DESCRIPTION]] - 角色外貌描述&#10;[[PERSONALITY]] - 角色性格&#10;[[STYLE]] - 项目风格描述"
            />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span>场景提示词模板</span>
              <el-tooltip placement="top">
                <template #content>
                  可用变量：<br/>
                  [[NAME]] - 场景名称<br/>
                  [[DESCRIPTION]] - 场景描述<br/>
                  [[LOCATION]] - 地点<br/>
                  [[TIME]] - 时间（白天/夜晚/黄昏等）<br/>
                  [[STYLE]] - 项目风格描述
                </template>
                <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
            <el-input 
              v-model="prompts.scene_ref_prompt" 
              type="textarea" 
              :rows="8"
              placeholder="编辑场景参考图生成的提示词模板...&#10;&#10;可用变量:&#10;[[NAME]] - 场景名称&#10;[[DESCRIPTION]] - 场景描述&#10;[[LOCATION]] - 地点&#10;[[TIME]] - 时间（白天/夜晚/黄昏等）&#10;[[STYLE]] - 项目风格描述"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showPromptDialog = false">取消</el-button>
          <el-button type="primary" @click="savePrompts" :loading="savingPrompts">保存</el-button>
        </template>
      </el-dialog>

      <!-- 编辑单个Prompt对话框 -->
      <el-dialog v-model="showEditItemPromptDialog" title="编辑提示词" width="600px">
        <el-form label-position="top">
          <el-form-item label="当前提示词">
            <el-input 
              v-model="editItemPromptForm.prompt" 
              type="textarea" 
              :rows="6"
              placeholder="输入提示词..."
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showEditItemPromptDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmEditItemPrompt" :loading="editItemPromptForm.saving">
            保存并重新生成
          </el-button>
        </template>
      </el-dialog>

      <!-- 重新生成对话框 -->
      <el-dialog v-model="showRegenerateDialog" title="重新生成选项" width="500px">
        <el-form :model="regenerateForm" label-width="100px">
          <el-form-item label="方式">
            <el-radio-group v-model="regenerateForm.method">
              <el-radio label="seed">改Seed</el-radio>
              <el-radio label="prompt">改提示词</el-radio>
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
          <el-button @click="showRegenerateDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmRegenerate" :loading="regenerating">重新生成</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled, Refresh } from '@element-plus/icons-vue'
import { scriptApi, referenceApi } from '../api'
import { useProjectStore } from '../stores/project'
import axios from 'axios'

const projectStore = useProjectStore()
const activeTab = ref('characters')
const characters = ref([])
const scenes = ref([])
const loading = ref(false)
const generating = ref(false)

// 提示词编辑
const showPromptDialog = ref(false)
const savingPrompts = ref(false)
const prompts = ref({
  character_ref_prompt: '',
  scene_ref_prompt: ''
})

// 编辑单个Prompt
const showEditItemPromptDialog = ref(false)
const editItemPromptForm = ref({
  prompt: '',
  saving: false
})

// 重新生成
const showRegenerateDialog = ref(false)
const regenerating = ref(false)
const regenerateForm = ref({
  method: 'seed',
  new_seed: Math.floor(Math.random() * 1000000),
  new_prompt: ''
})
const currentItem = ref(null)
const currentItemType = ref('')

let timer = null

const getCurrentVersion = (item) => {
  const versions = item.versions || []
  const currentVer = item.current_version || 1
  return versions[currentVer - 1]
}

const getCurrentImage = (item) => {
  const version = getCurrentVersion(item)
  return version?.path
}

const getImageUrl = (path) => {
  if (!path) return ''
  // 将绝对路径转换为相对于 static 目录的路径
  // 例如: /home/user/animation_projects/project_xxx/02_references/characters/char_001.png
  // 转换为: project_xxx/02_references/characters/char_001.png
  const parts = path.split('animation_projects/')
  if (parts.length > 1) {
    return `http://localhost:8000/static/${parts[1]}`
  }
  return path
}

const handleImageError = (e) => {
  console.error('图片加载失败:', e.target.src)
}

const fetchData = async () => {
  if (!projectStore.projectId) return
  loading.value = true
  try {
    const [charRes, sceneRes] = await Promise.all([
      scriptApi.getCharacters(projectStore.projectId),
      scriptApi.getScenes(projectStore.projectId)
    ])
    characters.value = charRes.data
    scenes.value = sceneRes.data
  } catch (e) {
    console.error('获取数据失败:', e)
  } finally {
    loading.value = false
  }
}

const generateReferences = async () => {
  if (!projectStore.projectId) return
  generating.value = true
  try {
    await referenceApi.generate(projectStore.projectId)
    ElMessage.success('生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    generating.value = false
  }
}

const fetchPrompts = async () => {
  try {
    const res = await axios.get('/api/config/prompts')
    prompts.value = res.data
  } catch (e) {
    console.error('获取提示词失败:', e)
  }
}

const savePrompts = async () => {
  savingPrompts.value = true
  try {
    await axios.put('/api/config/prompts', prompts.value)
    ElMessage.success('提示词已保存')
    showPromptDialog.value = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    savingPrompts.value = false
  }
}

const openRegenerateDialog = (item, type) => {
  currentItem.value = item
  currentItemType.value = type
  regenerateForm.value = {
    method: 'seed',
    new_seed: Math.floor(Math.random() * 1000000),
    new_prompt: ''
  }
  showRegenerateDialog.value = true
}

const confirmRegenerate = async () => {
  if (!projectStore.projectId || !currentItem.value) return
  
  regenerating.value = true
  try {
    const id = currentItemType.value === 'character' 
      ? currentItem.value.character_id 
      : currentItem.value.scene_id
    
    await axios.post(
      `/api/projects/${projectStore.projectId}/${currentItemType.value}s/${id}/regenerate`,
      regenerateForm.value
    )
    ElMessage.success('重新生成任务已提交')
    showRegenerateDialog.value = false
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    regenerating.value = false
  }
}

const regenerateCharacter = async (char) => {
  currentItem.value = char
  currentItemType.value = 'character'
  regenerateForm.value = {
    method: 'seed',
    new_seed: Math.floor(Math.random() * 1000000),
    new_prompt: ''
  }
  await confirmRegenerate()
}

const regenerateScene = async (scene) => {
  currentItem.value = scene
  currentItemType.value = 'scene'
  regenerateForm.value = {
    method: 'seed',
    new_seed: Math.floor(Math.random() * 1000000),
    new_prompt: ''
  }
  await confirmRegenerate()
}

// 打开编辑单个Prompt对话框
const openEditPromptDialog = (item, type) => {
  currentItem.value = item
  currentItemType.value = type
  const version = getCurrentVersion(item)
  editItemPromptForm.value.prompt = version?.prompt || ''
  showEditItemPromptDialog.value = true
}

// 确认编辑单个Prompt
const confirmEditItemPrompt = async () => {
  if (!editItemPromptForm.value.prompt.trim()) {
    ElMessage.warning('请输入提示词')
    return
  }
  
  editItemPromptForm.value.saving = true
  try {
    const id = currentItemType.value === 'character'
      ? currentItem.value.character_id
      : currentItem.value.scene_id
    
    // 先保存提示词，然后重新生成
    await axios.post(
      `/api/projects/${projectStore.projectId}/${currentItemType.value}s/${id}/regenerate`,
      {
        method: 'prompt',
        new_prompt: editItemPromptForm.value.prompt
      }
    )
    
    showEditItemPromptDialog.value = false
    ElMessage.success('提示词已保存，重新生成任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    editItemPromptForm.value.saving = false
  }
}

onMounted(() => {
  fetchData()
  fetchPrompts()
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
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  padding: 20px 0;
}

.image-card {
  break-inside: avoid;
}

.image-wrapper {
  height: 200px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.reference-image {
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

.image-info .description,
.image-info .location {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #666;
}

.actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-preview {
  margin: 8px 0;
  padding: 6px 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
}

.prompt-text {
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
