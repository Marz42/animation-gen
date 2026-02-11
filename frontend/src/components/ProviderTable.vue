<template>
  <div class="provider-table">
    <!-- 当前默认提供商提示 -->
    <div v-if="defaultProvider" class="default-provider-banner">
      <el-alert
        :title="`当前默认${type.toUpperCase()}提供商: ${defaultProvider.name}`"
        type="success"
        :closable="false"
        show-icon
      >
        <template #default>
          <div class="default-info">
            <span>{{ defaultProvider.base_url }}</span>
            <span v-if="defaultProvider.model">| 模型: {{ defaultProvider.model }}</span>
            <span v-if="defaultProvider.latency">| 延迟: {{ defaultProvider.latency }}ms</span>
          </div>
        </template>
      </el-alert>
    </div>
    
    <el-empty v-if="!providers || providers.length === 0" description="暂无提供商" />
    
    <el-table v-else :data="providers" style="width: 100%" v-loading="loading"
              :row-class-name="getRowClassName">
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <div class="status-tags">
            <el-tag v-if="row.is_builtin" type="primary" size="small" effect="dark">
              <el-icon><Monitor /></el-icon> 内置
            </el-tag>
            <el-tag v-else-if="row.is_default" type="success" size="small" effect="dark">
              <el-icon><Star /></el-icon> 默认
            </el-tag>
            <el-tag v-else-if="row.enabled" type="info" size="small">启用</el-tag>
            <el-tag v-else type="danger" size="small">禁用</el-tag>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="name" label="名称" min-width="150" />
      
      <el-table-column prop="base_url" label="Base URL" min-width="200">
        <template #default="{ row }">
          <el-tooltip :content="row.base_url" placement="top">
            <span class="ellipsis">{{ row.base_url }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      
      <el-table-column prop="model" label="模型" width="150">
        <template #default="{ row }">
          {{ row.model || '-' }}
        </template>
      </el-table-column>
      
      <el-table-column prop="verified" label="验证" width="90">
        <template #default="{ row }">
          <el-tag 
            :type="getVerifyType(row)" 
            size="small"
            v-if="row.verified !== undefined && row.verified !== null"
          >
            {{ getVerifyText(row) }}
          </el-tag>
          <el-tag type="info" size="small" v-else>未验证</el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="latency" label="延迟" width="80">
        <template #default="{ row }">
          <span v-if="row.latency">{{ row.latency }}ms</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <!-- 内置提供商显示特殊提示 -->
          <el-tooltip v-if="row.is_builtin" content="内置提供商来自配置文件，请在配置文件中修改" placement="top">
            <el-tag type="info" size="small" effect="plain">配置文件</el-tag>
          </el-tooltip>
          
          <!-- 非内置提供商的操作按钮 -->
          <template v-else>
            <el-button 
              v-if="!row.is_default && row.enabled" 
              type="warning" 
              size="small" 
              @click="$emit('setDefault', row)"
              :loading="settingDefault === row.id"
            >
              <el-icon><Star /></el-icon> 设为默认
            </el-button>
            <el-tag v-else-if="row.is_default" type="success" size="small" effect="plain">
              <el-icon><StarFilled /></el-icon> 当前默认
            </el-tag>
          </template>
          
          <el-button 
            type="primary" 
            size="small" 
            @click="$emit('edit', row)"
            :disabled="row.is_builtin"
          >
            {{ row.is_builtin ? '只读' : '编辑' }}
          </el-button>
          
          <el-button 
            type="success" 
            size="small" 
            @click="$emit('verify', row)" 
            :loading="verifying === row.id"
          >
            验证
          </el-button>
          
          <el-button 
            type="danger" 
            size="small" 
            @click="$emit('delete', row)" 
            :disabled="row.is_default || row.is_builtin"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Star, StarFilled, Monitor } from '@element-plus/icons-vue'

const props = defineProps({
  providers: {
    type: Array,
    default: () => []
  },
  type: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  settingDefault: {
    type: String,
    default: null
  }
})

defineEmits(['edit', 'delete', 'verify', 'setDefault'])

const verifying = ref(null)

// 计算当前默认提供商
const defaultProvider = computed(() => {
  return props.providers.find(p => p.is_default) || null
})

// 获取行样式类名
const getRowClassName = ({ row }) => {
  if (row.is_builtin) {
    return 'builtin-provider-row'
  }
  if (row.is_default) {
    return 'default-provider-row'
  }
  return ''
}

const getVerifyType = (row) => {
  if (row.verified === true) return 'success'
  if (row.verified === false) return 'danger'
  return 'info'
}

const getVerifyText = (row) => {
  if (row.verified === true) return '已验证'
  if (row.verified === false) return '验证失败'
  return '未验证'
}
</script>

<style scoped>
.provider-table {
  padding: 10px 0;
}

.default-provider-banner {
  margin-bottom: 15px;
}

.default-info {
  margin-top: 5px;
  font-size: 13px;
  color: #666;
}

.default-info span {
  margin-right: 15px;
}

.status-tags {
  display: flex;
  gap: 5px;
}

.ellipsis {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.default-provider-row) {
  background-color: #f0f9ff !important;
}

:deep(.default-provider-row:hover) {
  background-color: #e6f7ff !important;
}

:deep(.builtin-provider-row) {
  background-color: #f6ffed !important;
}

:deep(.builtin-provider-row:hover) {
  background-color: #d9f7be !important;
}
</style>