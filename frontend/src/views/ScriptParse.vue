<template>
  <div class="script-page">
    <el-alert 
      v-if="!projectStore.hasProject" 
      title="请先选择项目" 
      type="warning" 
      show-icon 
      :closable="false"
    />
    
    <template v-else>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card class="box-card">
            <template #header>
              <div class="card-header">
                <span>项目信息</span>
              </div>
            </template>
            <div class="project-info">
              <p><strong>名称:</strong> {{ projectStore.currentProject?.name }}</p>
              <p><strong>ID:</strong> {{ projectStore.currentProject?.project_id?.substring(0, 12) }}...</p>
              <p><strong>状态:</strong> 
                <el-tag :type="statusType(projectStore.currentProject?.current_stage)">
                  {{ projectStore.currentProject?.current_stage }}
                </el-tag>
              </p>
              <p><strong>进度:</strong> {{ projectStore.currentProject?.progress_percentage?.toFixed(1) }}%</p>
            </div>
            <el-button 
              type="primary" 
              class="parse-btn" 
              @click="startParse"
              :loading="parsing"
              :disabled="projectStore.currentProject?.current_stage === 'extracting'"
            >
              {{ projectStore.currentProject?.current_stage === 'extracting' ? '解析中...' : '开始解析剧本' }}
            </el-button>
            <el-button 
              class="parse-btn" 
              @click="showPromptDialog = true"
              style="margin-top: 10px;"
            >
              编辑解析提示词
            </el-button>
          </el-card>
        </el-col>

        <el-col :span="16">
          <el-card class="box-card">
            <template #header>
              <div class="card-header">
                <span>解析结果</span>
                <el-button type="primary" size="small" @click="fetchData" :loading="loading">
                  <el-icon><Refresh /></el-icon>刷新
                </el-button>
              </div>
            </template>
            
            <el-tabs v-model="activeTab">
              <el-tab-pane label="角色列表" name="characters">
                <el-table :data="characters" style="width: 100%" v-loading="loading">
                  <el-table-column prop="character_id" label="ID" width="100" />
                  <el-table-column prop="name" label="名称" />
                  <el-table-column prop="description" label="描述" show-overflow-tooltip />
                  <el-table-column prop="personality" label="性格" show-overflow-tooltip />
                  <el-table-column prop="status" label="状态" width="100">
                    <template #default="{ row }">
                      <el-tag :type="row.status === 'approved' ? 'success' : 'info'">
                        {{ row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
              
              <el-tab-pane label="场景列表" name="scenes">
                <el-table :data="scenes" style="width: 100%" v-loading="loading">
                  <el-table-column prop="scene_id" label="ID" width="100" />
                  <el-table-column prop="name" label="名称" />
                  <el-table-column prop="location" label="地点" />
                  <el-table-column prop="time" label="时间" />
                  <el-table-column prop="description" label="描述" show-overflow-tooltip />
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <!-- 提示词编辑对话框 -->
    <el-dialog v-model="showPromptDialog" title="编辑剧本解析提示词" width="800px">
      <el-form :model="prompts" label-width="120px">
        <el-form-item label="角色提取提示词">
          <el-input 
            v-model="prompts.character_extraction" 
            type="textarea" 
            :rows="8"
            placeholder="编辑角色提取的提示词..."
          />
        </el-form-item>
        <el-form-item label="场景提取提示词">
          <el-input 
            v-model="prompts.scene_extraction" 
            type="textarea" 
            :rows="8"
            placeholder="编辑场景提取的提示词..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPromptDialog = false">取消</el-button>
        <el-button type="primary" @click="savePrompts" :loading="savingPrompts">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { scriptApi } from '../api'
import { useProjectStore } from '../stores/project'
import axios from 'axios'

const projectStore = useProjectStore()
const activeTab = ref('characters')
const characters = ref([])
const scenes = ref([])
const loading = ref(false)
const parsing = ref(false)

// 提示词编辑
const showPromptDialog = ref(false)
const savingPrompts = ref(false)
const prompts = ref({
  character_extraction: '',
  scene_extraction: ''
})

let timer = null

const statusType = (stage) => {
  const map = {
    'draft': 'info',
    'extracting': 'warning',
    'pending_review_extraction': 'success',
  }
  return map[stage] || 'info'
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

const startParse = async () => {
  if (!projectStore.projectId) return
  parsing.value = true
  try {
    await scriptApi.parse(projectStore.projectId)
    ElMessage.success('解析任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    parsing.value = false
  }
}

const fetchPrompts = async () => {
  try {
    const res = await axios.get('/api/config/prompts')
    prompts.value = {
      character_extraction: res.data.character_extraction || '',
      scene_extraction: res.data.scene_extraction || ''
    }
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
.script-page {
  padding: 0;
}

.project-info p {
  margin: 10px 0;
}

.parse-btn {
  width: 100%;
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
