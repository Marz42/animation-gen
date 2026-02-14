<template>
  <div class="prompt-manager-page">
    <!-- 页面头部 -->
    <el-card class="header-card">
      <div class="header-content">
        <div class="header-left">
          <h2>🔧 系统提示词管理</h2>
          <p class="subtitle">管理所有 LLM 提示词模板，支持占位符变量</p>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="saveAllPrompts" :loading="saving">
            <el-icon><Check /></el-icon>
            保存全部
          </el-button>
          <el-button @click="resetToDefault" :loading="resetting">
            <el-icon><RefreshLeft /></el-icon>
            重置默认
          </el-button>
          <el-button @click="exportPrompts">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
          <el-button @click="showImportDialog = true">
            <el-icon><Upload /></el-icon>
            导入
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 阶段1: 剧本解析 -->
    <el-card class="stage-card">
      <template #header>
        <div class="stage-header">
          <span class="stage-title">📑 阶段1: 剧本解析</span>
          <el-tag type="info">提取角色和场景</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">角色提取提示词</span>
              <el-tooltip content="用于从剧本中提取角色信息" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.character_extraction"
              type="textarea"
              :rows="12"
              placeholder="输入角色提取提示词..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.script" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('character_extraction', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">场景提取提示词</span>
              <el-tooltip content="用于从剧本中提取场景信息" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.scene_extraction"
              type="textarea"
              :rows="12"
              placeholder="输入场景提取提示词..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.script" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('scene_extraction', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 阶段3: 参考图生成 -->
    <el-card class="stage-card">
      <template #header>
        <div class="stage-header">
          <span class="stage-title">🎨 阶段3: 参考图生成</span>
          <el-tag type="info">生成角色和场景参考图</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">角色参考图提示词</span>
              <el-tooltip content="用于生成角色参考图的提示词" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.character_ref_prompt"
              type="textarea"
              :rows="10"
              placeholder="输入角色参考图提示词..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.character" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('character_ref_prompt', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">场景参考图提示词</span>
              <el-tooltip content="用于生成场景参考图的提示词" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.scene_ref_prompt"
              type="textarea"
              :rows="10"
              placeholder="输入场景参考图提示词..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.scene" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('scene_ref_prompt', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 阶段4: 分镜设计 -->
    <el-card class="stage-card">
      <template #header>
        <div class="stage-header">
          <span class="stage-title">🎬 阶段4: 分镜设计</span>
          <el-tag type="info">自动生成分镜</el-tag>
        </div>
      </template>
      
      <div class="prompt-editor">
        <div class="editor-header">
          <span class="editor-title">分镜设计提示词</span>
          <el-tooltip content="用于为每个场景设计分镜" placement="top">
            <el-icon><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <el-input
          v-model="prompts.shot_design"
          type="textarea"
          :rows="14"
          placeholder="输入分镜设计提示词..."
        />
        <div class="placeholders-bar">
          <span class="placeholder-label">可用占位符:</span>
          <el-tag 
            v-for="p in placeholders.shot" 
            :key="p"
            size="small"
            class="placeholder-tag"
            @click="insertPlaceholder('shot_design', p)"
          >
            {{ p }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 阶段5-6: 提示词生成 -->
    <el-card class="stage-card">
      <template #header>
        <div class="stage-header">
          <span class="stage-title">🖼️ 阶段5-6: 提示词生成</span>
          <el-tag type="info">首帧图片和视频提示词</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">图片提示词模板</span>
              <el-tooltip content="用于生成每个分镜的图片提示词" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.image_prompt"
              type="textarea"
              :rows="12"
              placeholder="输入图片提示词模板..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.image" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('image_prompt', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="prompt-editor">
            <div class="editor-header">
              <span class="editor-title">视频提示词模板</span>
              <el-tooltip content="用于生成每个分镜的视频提示词" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </div>
            <el-input
              v-model="prompts.video_prompt"
              type="textarea"
              :rows="12"
              placeholder="输入视频提示词模板..."
            />
            <div class="placeholders-bar">
              <span class="placeholder-label">可用占位符:</span>
              <el-tag 
                v-for="p in placeholders.video" 
                :key="p"
                size="small"
                class="placeholder-tag"
                @click="insertPlaceholder('video_prompt', p)"
              >
                {{ p }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 占位符说明卡片 -->
    <el-card class="stage-card">
      <template #header>
        <div class="stage-header">
          <span class="stage-title">📖 占位符说明</span>
          <el-tag type="success">快速参考</el-tag>
        </div>
      </template>
      
      <el-collapse>
        <el-collapse-item title="通用占位符" name="1">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="[[SCRIPT]]">完整剧本原文内容</el-descriptions-item>
            <el-descriptions-item label="[[STYLE]]">项目整体风格描述</el-descriptions-item>
            <el-descriptions-item label="[[NAME]]">角色/场景名称</el-descriptions-item>
            <el-descriptions-item label="[[DESCRIPTION]]">角色外貌/场景描述</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
        <el-collapse-item title="角色相关" name="2">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="[[PERSONALITY]]">角色性格特点</el-descriptions-item>
            <el-descriptions-item label="[[CHARACTERS]]">格式化角色列表</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
        <el-collapse-item title="场景相关" name="3">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="[[LOCATION]]">场景地点</el-descriptions-item>
            <el-descriptions-item label="[[TIME]]">场景时间（白天/夜晚等）</el-descriptions-item>
            <el-descriptions-item label="[[SCENE_NAME]]">场景名称</el-descriptions-item>
            <el-descriptions-item label="[[SCENE_DESCRIPTION]]">场景描述</el-descriptions-item>
            <el-descriptions-item label="[[SCENE_REF]]">场景参考描述</el-descriptions-item>
            <el-descriptions-item label="[[SCRIPT_SEGMENT]]">场景剧本片段</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
        <el-collapse-item title="分镜相关" name="4">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="[[SHOT_DESCRIPTION]]">分镜描述</el-descriptions-item>
            <el-descriptions-item label="[[ACTION]]">分镜动作描述</el-descriptions-item>
            <el-descriptions-item label="[[CAMERA_MOVEMENT]]">镜头运动</el-descriptions-item>
            <el-descriptions-item label="[[DURATION]]">持续时间</el-descriptions-item>
            <el-descriptions-item label="[[IMAGE_PROMPT]]">首帧图片提示词</el-descriptions-item>
          </el-descriptions>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入提示词配置" width="600px">
      <el-alert
        title="请粘贴之前导出的JSON配置"
        type="info"
        :closable="false"
        style="margin-bottom: 15px"
      />
      <el-input
        v-model="importContent"
        type="textarea"
        :rows="15"
        placeholder="粘贴JSON配置..."
      />
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="importPrompts" :loading="importing">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, RefreshLeft, Download, Upload, QuestionFilled } from '@element-plus/icons-vue'
import { promptApi } from '../api'

// 提示词数据
const prompts = ref({
  character_extraction: '',
  scene_extraction: '',
  character_ref_prompt: '',
  scene_ref_prompt: '',
  shot_design: '',
  image_prompt: '',
  video_prompt: ''
})

// 占位符定义
const placeholders = {
  script: ['[[SCRIPT]]'],
  character: ['[[NAME]]', '[[DESCRIPTION]]', '[[PERSONALITY]]', '[[STYLE]]'],
  scene: ['[[NAME]]', '[[DESCRIPTION]]', '[[LOCATION]]', '[[TIME]]', '[[STYLE]]'],
  shot: ['[[SCENE_NAME]]', '[[SCENE_DESCRIPTION]]', '[[CHARACTERS]]', '[[SCRIPT_SEGMENT]]'],
  image: ['[[SHOT_DESCRIPTION]]', '[[CHARACTERS]]', '[[SCENE_REF]]', '[[STYLE]]'],
  video: ['[[SCENE_DESCRIPTION]]', '[[IMAGE_PROMPT]]', '[[CHARACTERS]]', '[[ACTION]]', '[[CAMERA_MOVEMENT]]', '[[DURATION]]']
}

// 默认提示词（用于重置）
const defaultPrompts = {
  character_extraction: `你是一位经验丰富的影视角色分析专家。请从以下剧本中提取所有主要角色信息。

## 角色识别标准
只识别在当前剧本中实际出场的角色（被提到但未出场的角色不要识别）：
- ✅ 有具体名字的角色（如"孙悟空"、"张三"）
- ✅ 有特定称号的主要角色（如"美猴王"、"老板"）
- ✅ 第一人称叙述中的"我"
- ❌ 群体角色（如"众猴"、"路人"、"士兵们"）
- ❌ 旁白/画外音

## 角色名称一致性
- 同一角色的不同称呼必须统一为一个名称
- 选择最常用、最正式的称呼
- 例如："石猴"后来被称为"美猴王"，统一使用"美猴王"

## 输出格式
{
  "characters": [
    {
      "name": "统一的角色名",
      "description": "剧本中描述的外貌特征（发型、服装、体型、面部特征等）",
      "personality": "剧本中体现的性格特点（内向/外向、勇敢/胆小、乐观/悲观等）"
    }
  ]
}

## 注意事项
1. 只提取剧本中明确提到的角色
2. 外貌和性格必须基于剧本中的描述，没有则留空
3. 不要编造剧本中没有的角色

剧本内容：
[[SCRIPT]]`,

  scene_extraction: `你是一位经验丰富的影视制片人和场景分析专家。请将以下剧本按"场景"维度进行结构化分解。

## 场景划分标准
按照"地点+时间段"的组合进行划分，满足以下任一条件就分为新场景：

### 地点变化
- 地点有细微变化就分为新场景
- 例如："山顶"→"山脚"→"山洞内部" = 三个不同场景

### 时间段变化
- 在同一地点，时间段变化也要分为新场景

### 场景合并原则
- 如果是室内场景，同一建筑物内的不同房间在连续剧情中应合并为一个大场景
- 如果是室外场景，地点跨度较大时仍需分开

## 输出格式
{
  "scenes": [
    {
      "name": "场景名称（地点，时间段）",
      "description": "场景的完整描述，包括环境、氛围、重要视觉元素",
      "location": "地点",
      "time": "时间段（白天/夜晚/傍晚/清晨/中午/深夜）",
      "characters": ["场景中出现的角色1", "角色2"],
      "script_segment": "该场景对应的原始剧本片段（从剧本原文中完整提取，保持原貌）"
    }
  ]
}

## 注意事项
1. 场景必须完整覆盖所有剧情，不能有遗漏
2. 相同场景+相同时间段的连续剧情应该合并为一个场景对象
3. 同一角色的名称在不同场景中要保持一致
4. 只识别实际出场的场景和角色

剧本内容：
[[SCRIPT]]`,

  character_ref_prompt: `你是一名资深的角色设计师和AI提示词描述师。

基于以下角色描述和整体风格，生成一个用于AI图片生成的详细提示词。
提示词应该描述角色的完整外观，适合作为角色参考图。

角色信息：
- 名称: [[NAME]]
- 描述: [[DESCRIPTION]]
- 性格: [[PERSONALITY]]

整体风格: [[STYLE]]

请只输出提示词本身，不要有其他说明。`,

  scene_ref_prompt: `你是一名经验丰富的场景美术设计师和概念艺术家。

基于以下场景描述和整体风格，生成一个用于AI图片生成的详细提示词。
提示词应该描述场景的氛围和环境，适合作为场景参考图（不要包含具体人物）。

场景信息：
- 名称: [[NAME]]
- 描述: [[DESCRIPTION]]
- 地点: [[LOCATION]]
- 时间: [[TIME]]

整体风格: [[STYLE]]

请只输出提示词本身，不要有其他说明。`,

  shot_design: `你是一名专业的分镜师。请为以下场景设计分镜。

场景信息：
- 场景名称: [[SCENE_NAME]]
- 场景描述: [[SCENE_DESCRIPTION]]
- 场景角色列表: [[CHARACTERS]]

剧本片段：
[[SCRIPT_SEGMENT]]

请设计3-5个分镜，每个分镜包含：
- 镜头类型 (wide/medium/close_up/extreme_close_up)
- 镜头运动 (static/pan/tilt/zoom/tracking)
- 持续时间 (重要：必须是以下之一: 4s/5s/6s/8s/10s)
- 画面描述
- 动作描述
- 对话（如果有）
- character_ids: 该分镜实际出场的角色ID列表（从上方场景角色列表中选择ID，不是名称）

重要规则：
- duration 字段必须是 "4s", "5s", "6s", "8s", 或 "10s" 之一
- 不要使用其他时长如 "2s", "3s", "7s", "9s" 等
- character_ids 必须填写，包含实际在该分镜出场的角色ID（如 "char_001"）
- 不能返回空列表，至少要有一个角色ID
- 根据剧情节奏选择合适的标准时长

请以JSON格式输出：
{
  "shots": [
    {
      "type": "wide",
      "camera_movement": "static",
      "duration": "5s",
      "description": "画面描述",
      "action": "动作描述",
      "dialogue": "对话内容或null",
      "character_ids": ["char_001", "char_002"]
    }
  ]
}`,

  image_prompt: `你是一名AI提示词工程师。基于以下信息生成图片生成提示词。

分镜描述: [[SHOT_DESCRIPTION]]
涉及角色: [[CHARACTERS]]
场景参考: [[SCENE_REF]]
整体风格: [[STYLE]]

请生成：
1. 正面提示词 (positive prompt)
2. 负面提示词 (negative prompt)

请以JSON格式输出：
{
  "positive": "详细的正面提示词",
  "negative": "负面提示词，如：bad anatomy, bad hands, worst quality..."
}`,

  video_prompt: `基于以下分镜信息生成视频生成提示词，重点描述运动和运镜。

剧本场景描述: [[SCENE_DESCRIPTION]]
首帧图片提示词: [[IMAGE_PROMPT]]
角色信息: [[CHARACTERS]]
分镜动作描述: [[ACTION]]
镜头运动: [[CAMERA_MOVEMENT]]
持续时间: [[DURATION]]

请生成一个详细的视频描述，包含：
1. 画面主体的动作描述
2. 相机运动方式
3. 光影变化（如果有）

只输出视频描述文本，不要解释。`
}

// 状态
const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const importing = ref(false)
const showImportDialog = ref(false)
const importContent = ref('')

// 加载提示词
const loadPrompts = async () => {
  loading.value = true
  try {
    const res = await promptApi.get()
    prompts.value = {
      character_extraction: res.data.character_extraction || '',
      scene_extraction: res.data.scene_extraction || '',
      character_ref_prompt: res.data.character_ref_prompt || '',
      scene_ref_prompt: res.data.scene_ref_prompt || '',
      shot_design: res.data.shot_design || '',
      image_prompt: res.data.image_prompt || '',
      video_prompt: res.data.video_prompt || ''
    }
    ElMessage.success('提示词加载成功')
  } catch (e) {
    ElMessage.error('加载提示词失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 保存所有提示词
const saveAllPrompts = async () => {
  saving.value = true
  try {
    await promptApi.update(prompts.value)
    ElMessage.success('所有提示词已保存')
  } catch (e) {
    ElMessage.error('保存失败')
    console.error(e)
  } finally {
    saving.value = false
  }
}

// 重置为默认值
const resetToDefault = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重置所有提示词为默认值吗？此操作不可恢复。',
      '确认重置',
      {
        confirmButtonText: '确定重置',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    resetting.value = true
    prompts.value = { ...defaultPrompts }
    await promptApi.update(prompts.value)
    ElMessage.success('已重置为默认值')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重置失败')
      console.error(e)
    }
  } finally {
    resetting.value = false
  }
}

// 导出提示词
const exportPrompts = () => {
  const data = JSON.stringify(prompts.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `prompts_config_${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('提示词配置已导出')
}

// 导入提示词
const importPrompts = async () => {
  if (!importContent.value.trim()) {
    ElMessage.warning('请输入配置内容')
    return
  }
  
  importing.value = true
  try {
    const data = JSON.parse(importContent.value)
    
    // 验证必要的字段
    const requiredFields = [
      'character_extraction', 'scene_extraction', 'character_ref_prompt',
      'scene_ref_prompt', 'shot_design', 'image_prompt', 'video_prompt'
    ]
    
    for (const field of requiredFields) {
      if (!(field in data)) {
        throw new Error(`缺少必要字段: ${field}`)
      }
    }
    
    prompts.value = data
    await promptApi.update(prompts.value)
    
    showImportDialog.value = false
    importContent.value = ''
    ElMessage.success('提示词配置已导入并保存')
  } catch (e) {
    ElMessage.error(`导入失败: ${e.message}`)
    console.error(e)
  } finally {
    importing.value = false
  }
}

// 插入占位符
const insertPlaceholder = (field, placeholder) => {
  const textarea = document.querySelector(`textarea[v-model="prompts.${field}"]`)
  if (textarea) {
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const value = prompts.value[field]
    prompts.value[field] = value.substring(0, start) + placeholder + value.substring(end)
    
    // 重新聚焦并设置光标位置
    setTimeout(() => {
      textarea.focus()
      textarea.setSelectionRange(start + placeholder.length, start + placeholder.length)
    }, 0)
  } else {
    // 如果无法获取textarea，直接追加到末尾
    prompts.value[field] += placeholder
  }
}

onMounted(() => {
  loadPrompts()
})
</script>

<style scoped>
.prompt-manager-page {
  padding-bottom: 40px;
}

.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.stage-card {
  margin-bottom: 20px;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stage-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.prompt-editor {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  background-color: #fafafa;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.editor-title {
  font-weight: 600;
  color: #606266;
  font-size: 14px;
}

.placeholders-bar {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.placeholder-label {
  font-size: 12px;
  color: #909399;
}

.placeholder-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.placeholder-tag:hover {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

:deep(.el-collapse-item__header) {
  font-size: 14px;
  font-weight: 600;
}
</style>
