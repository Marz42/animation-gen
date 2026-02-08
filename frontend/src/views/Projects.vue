<template>
  <div class="projects-page">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>项目管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>创建项目
          </el-button>
        </div>
      </template>

      <el-table :data="projects" style="width: 100%" v-loading="loading">
        <el-table-column prop="project_id" label="ID" width="120">
          <template #default="{ row }">
            {{ row.project_id?.substring(0, 8) }}...
          </template>
        </el-table-column>
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress_percentage" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percentage || 0" />
          </template>
        </el-table-column>
        <el-table-column label="统计" width="200">
          <template #default="{ row }">
            角色: {{ row.statistics?.total_characters || 0 }} | 
            场景: {{ row.statistics?.total_scenes || 0 }} | 
            分镜: {{ row.statistics?.total_shots || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              :type="currentProject?.project_id === row.project_id ? 'success' : 'primary'" 
              size="small"
              @click="selectProject(row)"
            >
              {{ currentProject?.project_id === row.project_id ? '已选择' : '选择' }}
            </el-button>
            <el-button type="danger" size="small" @click="deleteProject(row.project_id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建新项目" width="600px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="项目名称" required>
          <el-input v-model="createForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="风格描述" required>
          <el-input 
            v-model="createForm.style_description" 
            type="textarea" 
            :rows="2"
            placeholder="例如：高精度日系作画风格，参考新海诚动画电影"
          />
        </el-form-item>
        <el-form-item label="剧本内容" required>
          <el-input 
            v-model="createForm.script_content" 
            type="textarea" 
            :rows="10"
            placeholder="# 第一幕&#10;&#10;## 场景1：教室..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '../api'
import { useProjectStore } from '../stores/project'

const projectStore = useProjectStore()
const projects = ref([])
const loading = ref(false)
const showCreateDialog = ref(false)
const creating = ref(false)
const currentProject = ref(null)

const createForm = ref({
  name: '',
  style_description: '',
  script_content: ''
})

const statusType = (status) => {
  const map = {
    'draft': 'info',
    'extracting': 'warning',
    'generating_refs': 'warning',
    'designing_shots': 'warning',
    'generating_frames': 'warning',
    'generating_videos': 'warning',
    'completed': 'success',
    'error': 'danger'
  }
  return map[status] || 'info'
}

const fetchProjects = async () => {
  loading.value = true
  try {
    const res = await projectApi.list()
    projects.value = res.data
    projectStore.setProjects(res.data)
  } catch (e) {
    ElMessage.error('获取项目列表失败')
  } finally {
    loading.value = false
  }
}

const selectProject = (project) => {
  currentProject.value = project
  projectStore.setCurrentProject(project)
  ElMessage.success(`已选择项目: ${project.name}`)
}

const deleteProject = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这个项目吗？', '提示', { type: 'warning' })
    await projectApi.delete(id)
    ElMessage.success('删除成功')
    if (currentProject.value?.project_id === id) {
      currentProject.value = null
      projectStore.clearProject()
    }
    fetchProjects()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const createProject = async () => {
  if (!createForm.value.name || !createForm.value.script_content) {
    ElMessage.warning('请填写完整信息')
    return
  }
  creating.value = true
  try {
    await projectApi.create(createForm.value)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', style_description: '', script_content: '' }
    fetchProjects()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(fetchProjects)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
