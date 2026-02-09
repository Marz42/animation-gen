<template>
  <div class="provider-table">
    <el-empty v-if="!providers || providers.length === 0" description="暂无提供商" />
    
    <el-table v-else :data="providers" style="width: 100%" v-loading="loading">
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
      
      <el-table-column prop="enabled" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column prop="verified" label="验证状态" width="100">
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
      
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="$emit('edit', row)">
            编辑
          </el-button>
          <el-button type="success" size="small" @click="$emit('verify', row)" :loading="verifying === row.id">
            验证
          </el-button>
          <el-button type="danger" size="small" @click="$emit('delete', row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
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
  }
})

defineEmits(['edit', 'delete', 'verify'])

const verifying = ref(null)

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

.ellipsis {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>