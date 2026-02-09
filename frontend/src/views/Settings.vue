<template>
  <div class="settings-page">
    <!-- 配置导入/导出卡片 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>配置管理</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="config-section">
            <h4>导出配置</h4>
            <p class="desc">导出所有配置到JSON文件，包括提示词和API提供商配置</p>
            <el-button type="primary" @click="exportConfig" :loading="exporting">
              <el-icon><Download /></el-icon>导出配置
            </el-button>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="config-section">
            <h4>导入配置</h4>
            <p class="desc">从JSON文件导入配置</p>
            <el-upload
              action="#"
              :auto-upload="false"
              :on-change="handleFileChange"
              accept=".json"
              :show-file-list="false"
            >
              <el-button type="primary" :loading="importing">
                <el-icon><Upload /></el-icon>选择文件导入
              </el-button>
            </el-upload>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- API提供商管理卡片 -->
    <el-card class="box-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>API提供商管理</span>
          <el-button type="primary" @click="showAddDialog">
            <el-icon><Plus /></el-icon>添加提供商
          </el-button>
        </div>
      </template>

      <!-- 提供商列表 -->
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="LLM" name="llm">
          <provider-table 
            :providers="providers.llm || []" 
            type="llm"
            @edit="editProvider"
            @delete="deleteProvider"
            @verify="verifyProvider"
          />
        </el-tab-pane>
        <el-tab-pane label="Image" name="image">
          <provider-table 
            :providers="providers.image || []" 
            type="image"
            @edit="editProvider"
            @delete="deleteProvider"
            @verify="verifyProvider"
          />
        </el-tab-pane>
        <el-tab-pane label="Video" name="video">
          <provider-table 
            :providers="providers.video || []" 
            type="video"
            @edit="editProvider"
            @delete="deleteProvider"
            @verify="verifyProvider"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加/编辑提供商对话框 -->
    <el-dialog 
      v-model="dialogVisible" 
      :title="isEditing ? '编辑提供商' : '添加提供商'" 
      width="700px"
      destroy-on-close
    >
      <!-- CURL解析区域 -->
      <el-collapse v-if="!isEditing" style="margin-bottom: 20px;">
        <el-collapse-item title="从CURL命令导入">
          <el-input
            v-model="curlCommand"
            type="textarea"
            :rows="4"
            placeholder="粘贴CURL命令，例如: curl -X POST https://api.example.com/v1/chat/completions -H 'Authorization: Bearer sk-xxx' -d '{...}'"
          />
          <el-button type="primary" @click="parseCurl" :loading="parsingCurl" style="margin-top: 10px;">
            解析CURL
          </el-button>
        </el-collapse-item>
      </el-collapse>

      <el-form :model="providerForm" :rules="providerRules" ref="providerFormRef" label-width="100px">
        <el-divider content-position="left">基础信息</el-divider>
        
        <el-form-item label="名称" prop="name">
          <el-input v-model="providerForm.name" placeholder="例如：OpenAI GPT-4" />
        </el-form-item>
        
        <el-form-item label="类型" prop="type">
          <el-select v-model="providerForm.type" placeholder="选择类型" style="width: 100%;">
            <el-option label="LLM" value="llm" />
            <el-option label="Image" value="image" />
            <el-option label="Video" value="video" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="启用状态">
          <el-switch v-model="providerForm.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>

        <el-divider content-position="left">API配置</el-divider>
        
        <el-form-item label="Base URL" prop="base_url">
          <el-input v-model="providerForm.base_url" placeholder="例如：https://api.openai.com/v1" />
        </el-form-item>
        
        <el-form-item label="API Key">
          <el-input 
            v-model="providerForm.api_key" 
            type="password" 
            show-password
            placeholder="输入API密钥"
          />
        </el-form-item>
        
        <el-form-item label="模型名称">
          <el-input v-model="providerForm.model" placeholder="例如：gpt-4（可选）" />
        </el-form-item>
        
        <el-form-item label="Endpoint">
          <el-input v-model="providerForm.endpoint" placeholder="例如：/chat/completions（可选）" />
        </el-form-item>
        
        <el-form-item label="超时时间(秒)">
          <el-input-number v-model="providerForm.timeout" :min="5" :max="300" />
        </el-form-item>

        <el-divider content-position="left">自定义请求头</el-divider>
        
        <div v-for="(value, key) in providerForm.headers" :key="key" class="header-item">
          <el-input v-model="headerKeys[key]" placeholder="Header名称" style="width: 150px;" />
          <el-input v-model="providerForm.headers[key]" placeholder="值" style="width: 200px; margin-left: 10px;" />
          <el-button type="danger" circle size="small" @click="removeHeader(key)" style="margin-left: 10px;">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <el-button type="primary" plain @click="addHeader" style="margin-top: 10px;">
          <el-icon><Plus /></el-icon>添加Header
        </el-button>

        <el-divider content-position="left">自定义字段</el-divider>
        
        <div v-for="(value, key) in providerForm.custom_fields" :key="'custom-'+key" class="header-item">
          <el-input v-model="customKeys[key]" placeholder="字段名" style="width: 150px;" />
          <el-input v-model="providerForm.custom_fields[key]" placeholder="值" style="width: 200px; margin-left: 10px;" />
          <el-button type="danger" circle size="small" @click="removeCustomField(key)" style="margin-left: 10px;">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <el-button type="primary" plain @click="addCustomField" style="margin-top: 10px;">
          <el-icon><Plus /></el-icon>添加自定义字段
        </el-button>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProvider" :loading="saving">
          {{ isEditing ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Upload, Plus, Delete } from '@element-plus/icons-vue'
import { configApi, providerApi } from '../api'
import ProviderTable from '../components/ProviderTable.vue'

// 配置导入导出
const exporting = ref(false)
const importing = ref(false)

const exportConfig = async () => {
  exporting.value = true
  try {
    const res = await configApi.export()
    const dataStr = JSON.stringify(res.data, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `animation-gen-config-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('配置导出成功')
  } catch (e) {
    ElMessage.error('配置导出失败')
  } finally {
    exporting.value = false
  }
}

const handleFileChange = async (file) => {
  if (!file) return
  
  importing.value = true
  try {
    const text = await file.raw.text()
    const config = JSON.parse(text)
    await configApi.import(config)
    ElMessage.success('配置导入成功')
    // 刷新提供商列表
    await loadProviders()
  } catch (e) {
    ElMessage.error(`配置导入失败: ${e.message}`)
  } finally {
    importing.value = false
  }
}

// 提供商管理
const activeTab = ref('llm')
const providers = ref({ llm: [], image: [], video: [] })
const loading = ref(false)

const loadProviders = async () => {
  loading.value = true
  try {
    const res = await providerApi.list()
    providers.value = res.data
  } catch (e) {
    ElMessage.error('获取提供商列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadProviders)

// 对话框
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const saving = ref(false)
const providerFormRef = ref(null)

const providerForm = reactive({
  name: '',
  type: 'llm',
  enabled: true,
  base_url: '',
  api_key: '',
  model: '',
  endpoint: '',
  headers: {},
  timeout: 60,
  custom_fields: {}
})

const headerKeys = reactive({})
const customKeys = reactive({})

const providerRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  base_url: [{ required: true, message: '请输入Base URL', trigger: 'blur' }]
}

const showAddDialog = () => {
  isEditing.value = false
  editingId.value = null
  Object.assign(providerForm, {
    name: '',
    type: activeTab.value,
    enabled: true,
    base_url: '',
    api_key: '',
    model: '',
    endpoint: '',
    headers: {},
    timeout: 60,
    custom_fields: {}
  })
  Object.keys(headerKeys).forEach(k => delete headerKeys[k])
  Object.keys(customKeys).forEach(k => delete customKeys[k])
  dialogVisible.value = true
}

const editProvider = (provider) => {
  isEditing.value = true
  editingId.value = provider.id
  Object.assign(providerForm, {
    name: provider.name,
    type: provider.type,
    enabled: provider.enabled,
    base_url: provider.base_url,
    api_key: provider.api_key,
    model: provider.model || '',
    endpoint: provider.endpoint || '',
    headers: { ...(provider.headers || {}) },
    timeout: provider.timeout || 60,
    custom_fields: { ...(provider.custom_fields || {}) }
  })
  // 同步headerKeys和customKeys
  Object.keys(headerKeys).forEach(k => delete headerKeys[k])
  Object.keys(provider.headers || {}).forEach(k => {
    headerKeys[k] = k
  })
  Object.keys(customKeys).forEach(k => delete customKeys[k])
  Object.keys(provider.custom_fields || {}).forEach(k => {
    customKeys[k] = k
  })
  dialogVisible.value = true
}

const saveProvider = async () => {
  const valid = await providerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    // 处理headers和custom_fields，使用实际的key值
    const headers = {}
    Object.entries(providerForm.headers).forEach(([oldKey, value]) => {
      const newKey = headerKeys[oldKey] || oldKey
      if (newKey) headers[newKey] = value
    })
    
    const customFields = {}
    Object.entries(providerForm.custom_fields).forEach(([oldKey, value]) => {
      const newKey = customKeys[oldKey] || oldKey
      if (newKey) customFields[newKey] = value
    })

    const data = {
      ...providerForm,
      headers,
      custom_fields: customFields
    }

    if (isEditing.value) {
      await providerApi.update(editingId.value, data)
      ElMessage.success('提供商更新成功')
    } else {
      await providerApi.create(data)
      ElMessage.success('提供商添加成功')
    }
    dialogVisible.value = false
    await loadProviders()
  } catch (e) {
    ElMessage.error(isEditing.value ? '更新失败' : '添加失败')
  } finally {
    saving.value = false
  }
}

const deleteProvider = async (provider) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除提供商 "${provider.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await providerApi.delete(provider.id)
    ElMessage.success('删除成功')
    await loadProviders()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const verifyProvider = async (provider) => {
  try {
    const res = await providerApi.verify(provider.id)
    if (res.data.valid) {
      ElMessage.success(`验证成功，延迟: ${res.data.latency}ms`)
    } else {
      ElMessage.error(`验证失败: ${res.data.error}`)
    }
    await loadProviders()
  } catch (e) {
    ElMessage.error('验证请求失败')
  }
}

// Headers管理
const addHeader = () => {
  const key = `key_${Date.now()}`
  providerForm.headers[key] = ''
  headerKeys[key] = ''
}

const removeHeader = (key) => {
  delete providerForm.headers[key]
  delete headerKeys[key]
}

// 自定义字段管理
const addCustomField = () => {
  const key = `field_${Date.now()}`
  providerForm.custom_fields[key] = ''
  customKeys[key] = ''
}

const removeCustomField = (key) => {
  delete providerForm.custom_fields[key]
  delete customKeys[key]
}

// CURL解析
const curlCommand = ref('')
const parsingCurl = ref(false)

const parseCurl = async () => {
  if (!curlCommand.value.trim()) {
    ElMessage.warning('请输入CURL命令')
    return
  }
  parsingCurl.value = true
  try {
    const res = await providerApi.parseCurl(curlCommand.value)
    const result = res.data
    
    // 自动填充表单
    if (result.base_url) providerForm.base_url = result.base_url
    if (result.endpoint) providerForm.endpoint = result.endpoint
    if (result.model) providerForm.model = result.model
    if (result.api_key) providerForm.api_key = result.api_key
    if (result.headers) {
      providerForm.headers = result.headers
      Object.keys(headerKeys).forEach(k => delete headerKeys[k])
      Object.keys(result.headers).forEach(k => {
        headerKeys[k] = k
      })
    }
    
    ElMessage.success('CURL解析成功，表单已自动填充')
  } catch (e) {
    ElMessage.error('解析失败')
  } finally {
    parsingCurl.value = false
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.config-section {
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.config-section h4 {
  margin: 0 0 10px 0;
  color: #303133;
}

.config-section .desc {
  color: #909399;
  font-size: 14px;
  margin-bottom: 15px;
}

.header-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
</style>