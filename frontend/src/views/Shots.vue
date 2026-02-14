<template>
  <div class="shots-page">
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
            <span>分镜设计</span>
            <div>
              <el-button 
                type="primary" 
                @click="designShots"
                :loading="designing"
              >
                自动生成分镜
              </el-button>
              <el-button @click="fetchData" :loading="loading">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
              <el-button type="info" @click="showPromptDialog = true">
                <el-icon><Setting /></el-icon>编辑提示词
              </el-button>
              <el-button type="success" @click="showExportDialog = true" :disabled="shots.length === 0">
                <el-icon><Document /></el-icon>导出分镜剧本
              </el-button>
            </div>
          </div>
        </template>

        <el-table 
          :data="shots" 
          style="width: 100%" 
          v-loading="loading"
          row-key="shot_id"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="shot-detail">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="分镜ID" :span="2">{{ row.shot_id }}</el-descriptions-item>
                  <el-descriptions-item label="场景">{{ row.scene_id }}</el-descriptions-item>
                  <el-descriptions-item label="镜头类型">
                    <el-tag size="small">{{ row.type }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="描述" :span="2">{{ row.description }}</el-descriptions-item>
                  <el-descriptions-item label="动作" :span="2">{{ row.action || '无' }}</el-descriptions-item>
                  <el-descriptions-item label="对话" :span="2">{{ row.dialogue || '无' }}</el-descriptions-item>
                  <el-descriptions-item label="角色" :span="2">
                    <el-tag v-for="charId in row.characters" :key="charId" size="small" class="mr-2">
                      {{ charId }}
                    </el-tag>
                  </el-descriptions-item>
                </el-descriptions>

                <!-- Prompt 显示和编辑 -->
                <el-divider>提示词</el-divider>
                <div class="prompt-section">
                  <div class="prompt-display" v-if="!row._editing">
                    <div class="prompt-block">
                      <div class="prompt-label">正面提示词 (Positive)</div>
                      <div class="prompt-content">{{ row.image_prompt?.positive || '未生成' }}</div>
                    </div>
                    <div class="prompt-block">
                      <div class="prompt-label">负面提示词 (Negative)</div>
                      <div class="prompt-content">{{ row.image_prompt?.negative || '未生成' }}</div>
                    </div>
                    <div class="prompt-actions">
                      <el-button type="primary" size="small" @click="startEditPrompt(row)">
                        <el-icon><Edit /></el-icon>编辑Prompt
                      </el-button>
                      <el-button type="warning" size="small" @click="showRedesignDialog(row)">
                        <el-icon><Refresh /></el-icon>重新设计
                      </el-button>
                    </div>
                  </div>

                  <!-- 编辑模式 -->
                  <div class="prompt-edit" v-else>
                    <el-form label-position="top">
                      <el-form-item label="正面提示词">
                        <el-input 
                          v-model="row._editForm.positive" 
                          type="textarea" 
                          :rows="4"
                          placeholder="输入正面提示词..."
                        />
                      </el-form-item>
                      <el-form-item label="负面提示词">
                        <el-input 
                          v-model="row._editForm.negative" 
                          type="textarea" 
                          :rows="2"
                          placeholder="输入负面提示词..."
                        />
                      </el-form-item>
                      <el-form-item>
                        <el-button type="primary" @click="savePrompt(row)" :loading="row._saving">
                          保存
                        </el-button>
                        <el-button @click="cancelEditPrompt(row)">取消</el-button>
                      </el-form-item>
                    </el-form>
                  </div>
                </div>

                <!-- 完整提示词显示 -->
                <el-divider>完整提示词</el-divider>
                <div class="display-prompt">
                  <pre>{{ row.display_prompt || '未生成' }}</pre>
                </div>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="shot_id" label="分镜ID" width="120" />
          <el-table-column prop="scene_id" label="场景" width="100" />
          <el-table-column prop="type" label="镜头类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="时长" width="80" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
          <el-table-column prop="action" label="动作" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ row.status || 'draft' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 重新设计对话框 -->
      <el-dialog v-model="redesignDialog.visible" title="重新设计分镜" width="500px">
        <el-form label-width="100px">
          <el-form-item label="当前描述">
            <div class="current-desc">{{ redesignDialog.shot?.description }}</div>
          </el-form-item>
          <el-form-item label="新描述">
            <el-input 
              v-model="redesignForm.new_prompt" 
              type="textarea" 
              :rows="4"
              placeholder="输入新的分镜描述，将根据此描述重新生成提示词..."
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="redesignDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="confirmRedesign" :loading="redesignForm.loading">
            重新设计
          </el-button>
        </template>
      </el-dialog>

      <!-- 编辑分镜设计提示词对话框 -->
      <el-dialog v-model="showPromptDialog" title="编辑分镜设计提示词" width="800px">
        <el-alert
          title="修改提示词后，下次生成分镜时将使用新提示词"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-alert
          title="提示词中可使用以下变量占位符来引用前阶段解析的场景、角色和剧本信息"
          type="warning"
          :closable="false"
          style="margin-bottom: 15px;"
        />
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <span>分镜设计提示词 (shot_design)</span>
              <el-tooltip placement="top">
                <template #content>
                  <div style="max-width: 350px;">
                    <b>可用占位符变量：</b><br/><br/>
                    [[SCENE_NAME]] - 场景名称<br/>
                    [[SCENE_DESCRIPTION]] - 场景描述<br/>
                    [[CHARACTERS]] - 角色列表（已格式化）<br/>
                    [[SCRIPT_SEGMENT]] - 该场景对应的剧本片段<br/><br/>
                    <b>重要：</b>LLM应返回的JSON中需包含 <code>character_ids</code> 字段，
                    用于指定每个分镜实际出场的角色ID列表，避免首帧生成时传入多余角色。
                  </div>
                </template>
                <el-icon style="margin-left: 4px; color: #909399;"><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
            <el-input 
              v-model="promptForm.shot_design" 
              type="textarea" 
              :rows="20"
              placeholder="输入分镜设计提示词...&#10;&#10;可用占位符变量:&#10;[[SCENE_NAME]] - 场景名称&#10;[[SCENE_DESCRIPTION]] - 场景描述&#10;[[CHARACTERS]] - 角色列表（已格式化）&#10;[[SCRIPT_SEGMENT]] - 该场景对应的剧本片段&#10;&#10;LLM应返回的JSON格式需包含:&#10;{&#10;  &quot;shots&quot;: [{&#10;    &quot;type&quot;: &quot;medium&quot;,&#10;    &quot;camera_movement&quot;: &quot;static&quot;,&#10;    &quot;duration&quot;: &quot;5s&quot;,&#10;    &quot;description&quot;: &quot;...&quot;,&#10;    &quot;action&quot;: &quot;...&quot;,&#10;    &quot;character_ids&quot;: [&quot;char_001&quot;, &quot;char_002&quot;]  // 该分镜实际出场的角色ID&#10;  }]&#10;}&#10;&#10;提示：使用双括号格式 [[VARIABLE]] 来插入变量"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showPromptDialog = false">取消</el-button>
          <el-button type="primary" @click="savePromptConfig" :loading="promptForm.saving">
            保存
          </el-button>
        </template>
      </el-dialog>
    </template>

    <!-- 导出分镜剧本对话框 -->
    <el-dialog v-model="exportDialog.visible" title="导出分镜剧本" width="600px">
      <el-alert
        title="将分镜数据与原始剧本结合，生成带有分镜设计和对话强调的新版剧本"
        type="info"
        :closable="false"
        style="margin-bottom: 15px;"
      />
      <el-form label-width="120px">
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio label="markdown">Markdown (.md)</el-radio>
            <el-radio label="html">HTML (.html)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="包含内容">
          <el-checkbox v-model="exportForm.include_dialogue">强调人物对话</el-checkbox>
          <el-checkbox v-model="exportForm.include_camera_info">镜头信息（类型/运动/时长）</el-checkbox>
          <el-checkbox v-model="exportForm.include_action">动作描述</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="previewExport" :loading="exportForm.previewLoading">
          预览
        </el-button>
        <el-button type="success" @click="confirmExport" :loading="exportForm.loading">
          导出
        </el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewDialog.visible" title="分镜剧本预览" width="900px" top="5vh">
      <div class="script-preview">
        <pre>{{ previewDialog.content }}</pre>
      </div>
      <template #footer>
        <el-button @click="previewDialog.visible = false">关闭</el-button>
        <el-button type="success" @click="downloadExport" :loading="exportForm.loading">
          下载文件
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled, Edit, Refresh, Document } from '@element-plus/icons-vue'
import { shotApi, promptApi } from '../api'
import { useProjectStore } from '../stores/project'

const projectStore = useProjectStore()
const shots = ref([])
const loading = ref(false)
const designing = ref(false)
let timer = null

// 导出对话框
const exportDialog = ref({
  visible: false
})

const exportForm = ref({
  format: 'markdown',
  include_dialogue: true,
  include_camera_info: true,
  include_action: true,
  loading: false,
  previewLoading: false
})

// 预览对话框
const previewDialog = ref({
  visible: false,
  content: ''
})

// 重新设计对话框
const redesignDialog = ref({
  visible: false,
  shot: null
})

const redesignForm = ref({
  new_prompt: '',
  loading: false
})

// 提示词编辑对话框
const showPromptDialog = ref(false)
const promptForm = ref({
  shot_design: '',
  saving: false
})

const statusType = (status) => {
  const map = {
    'draft': 'info',
    'frame_pending_review': 'warning',
    'frame_approved': 'success',
    'video_generating': 'warning',
    'completed': 'success'
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

const designShots = async () => {
  if (!projectStore.projectId) return
  designing.value = true
  try {
    await shotApi.design(projectStore.projectId)
    ElMessage.success('分镜设计任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    designing.value = false
  }
}

// 加载提示词配置
const loadPromptConfig = async () => {
  try {
    const res = await promptApi.get()
    promptForm.value.shot_design = res.data.shot_design || ''
  } catch (e) {
    console.error('加载提示词配置失败:', e)
  }
}

// 保存提示词配置
const savePromptConfig = async () => {
  promptForm.value.saving = true
  try {
    await promptApi.update({
      shot_design: promptForm.value.shot_design
    })
    ElMessage.success('提示词配置已保存')
    showPromptDialog.value = false
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    promptForm.value.saving = false
  }
}

// 开始编辑 Prompt
const startEditPrompt = (row) => {
  row._editing = true
  row._editForm = {
    positive: row.image_prompt?.positive || '',
    negative: row.image_prompt?.negative || ''
  }
  row._saving = false
}

// 取消编辑
const cancelEditPrompt = (row) => {
  row._editing = false
}

// 保存 Prompt
const savePrompt = async (row) => {
  row._saving = true
  try {
    await shotApi.editPrompt(projectStore.projectId, row.shot_id, {
      positive_prompt: row._editForm.positive,
      negative_prompt: row._editForm.negative
    })
    
    // 更新本地数据
    if (!row.image_prompt) row.image_prompt = {}
    row.image_prompt.positive = row._editForm.positive
    row.image_prompt.negative = row._editForm.negative
    row._editing = false
    
    ElMessage.success('提示词已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    row._saving = false
  }
}

// 显示重新设计对话框
const showRedesignDialog = (row) => {
  redesignDialog.value.shot = row
  redesignForm.value.new_prompt = row.description
  redesignDialog.value.visible = true
}

// 确认重新设计
const confirmRedesign = async () => {
  if (!redesignForm.value.new_prompt.trim()) {
    ElMessage.warning('请输入新的分镜描述')
    return
  }
  
  redesignForm.value.loading = true
  try {
    await shotApi.redesign(projectStore.projectId, redesignDialog.value.shot.shot_id, {
      new_prompt: redesignForm.value.new_prompt
    })
    
    redesignDialog.value.visible = false
    ElMessage.success('重新设计任务已提交')
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    redesignForm.value.loading = false
  }
}

// 导出分镜剧本
const confirmExport = async () => {
  exportForm.value.loading = true
  try {
    const res = await shotApi.exportShotScript(projectStore.projectId, {
      format: exportForm.value.format,
      include_dialogue: exportForm.value.include_dialogue,
      include_camera_info: exportForm.value.include_camera_info,
      include_action: exportForm.value.include_action
    })
    
    exportDialog.value.visible = false
    ElMessage.success(`分镜剧本已导出: ${res.data.filename}`)
    
    // 提供下载
    if (res.data.file_path) {
      // 创建下载链接
      const link = document.createElement('a')
      link.href = `/static/${res.data.file_path.split('animation_projects/')[1]}`
      link.download = res.data.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exportForm.value.loading = false
  }
}

// 预览分镜剧本
const previewExport = async () => {
  exportForm.value.previewLoading = true
  try {
    const res = await shotApi.previewShotScript(projectStore.projectId)
    previewDialog.value.content = res.data.content
    previewDialog.value.visible = true
  } catch (e) {
    ElMessage.error('预览失败')
  } finally {
    exportForm.value.previewLoading = false
  }
}

// 下载导出的文件
const downloadExport = async () => {
  exportForm.value.loading = true
  try {
    const res = await shotApi.exportShotScript(projectStore.projectId, {
      format: exportForm.value.format,
      include_dialogue: exportForm.value.include_dialogue,
      include_camera_info: exportForm.value.include_camera_info,
      include_action: exportForm.value.include_action
    })
    
    previewDialog.value.visible = false
    
    // 创建下载链接
    if (res.data.file_path) {
      const link = document.createElement('a')
      link.href = `/static/${res.data.file_path.split('animation_projects/')[1]}`
      link.download = res.data.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
    ElMessage.success('文件已下载')
  } catch (e) {
    ElMessage.error('下载失败')
  } finally {
    exportForm.value.loading = false
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

.shot-detail {
  padding: 20px;
  background: #f5f7fa;
}

.prompt-section {
  margin: 20px 0;
}

.prompt-display {
  background: #fff;
  padding: 15px;
  border-radius: 4px;
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
  background: #fff;
  padding: 15px;
  border-radius: 4px;
}

.display-prompt {
  background: #fff;
  padding: 15px;
  border-radius: 4px;
}

.display-prompt pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;
}

.current-desc {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  color: #606266;
}

.mr-2 {
  margin-right: 8px;
}

.script-preview {
  max-height: 60vh;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.script-preview pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
}
</style>
