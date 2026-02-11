import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 项目相关
export const projectApi = {
  list: () => api.get('/projects'),
  get: (id) => api.get(`/projects/${id}`),
  create: (data) => api.post('/projects', data),
  delete: (id) => api.delete(`/projects/${id}`),
}

// 剧本解析
export const scriptApi = {
  parse: (projectId) => api.post(`/projects/${projectId}/parse`),
  getCharacters: (projectId) => api.get(`/projects/${projectId}/characters`),
  getScenes: (projectId) => api.get(`/projects/${projectId}/scenes`),
  approveCharacter: (projectId, charId, approved, reason) => 
    api.post(`/projects/${projectId}/characters/${charId}/approve`, { approved, reason }),
}

// 参考图
export const referenceApi = {
  generate: (projectId) => api.post(`/projects/${projectId}/generate-references`),
  regenerateCharacter: (projectId, charId, data) => 
    api.post(`/projects/${projectId}/characters/${charId}/regenerate`, data),
  regenerateScene: (projectId, sceneId, data) => 
    api.post(`/projects/${projectId}/scenes/${sceneId}/regenerate`, data),
}

// 分镜
export const shotApi = {
  design: (projectId) => api.post(`/projects/${projectId}/design-shots`, {}),
  list: (projectId) => api.get(`/projects/${projectId}/shots`),
  get: (projectId, shotId) => api.get(`/projects/${projectId}/shots/${shotId}`),
  update: (projectId, shotId, data) => api.put(`/projects/${projectId}/shots/${shotId}`, data),
  editPrompt: (projectId, shotId, data) => api.post(`/projects/${projectId}/shots/${shotId}/edit-prompt`, data),
  redesign: (projectId, shotId, data) => api.post(`/projects/${projectId}/shots/${shotId}/redesign`, data),
}

// 首帧
export const keyframeApi = {
  generate: (projectId) => api.post(`/projects/${projectId}/generate-keyframes`),
  estimateCost: (projectId) => api.get(`/projects/${projectId}/cost-estimate`),
  approve: (projectId, shotId, approved, reason) => 
    api.post(`/projects/${projectId}/shots/${shotId}/approve-keyframe`, { approved, reason }),
  editPrompt: (projectId, shotId, data) => api.post(`/projects/${projectId}/shots/${shotId}/edit-prompt`, data),
  regenerate: (projectId, shotId, data) => api.post(`/projects/${projectId}/shots/${shotId}/regenerate-keyframe`, data),
}

// 视频
export const videoApi = {
  generate: (projectId, data) => api.post(`/projects/${projectId}/generate-videos`, data),
  list: (projectId) => api.get(`/projects/${projectId}/videos`),
  checkStatus: (projectId, shotId) => 
    api.post(`/projects/${projectId}/videos/${shotId}/check-status`, {}),
  // 视频Prompt相关
  generateVideoPrompt: (projectId, shotId, data = {}) => 
    api.post(`/projects/${projectId}/shots/${shotId}/generate-video-prompt`, data),
  getVideoPrompt: (projectId, shotId) => 
    api.get(`/projects/${projectId}/shots/${shotId}/video-prompt`),
  saveVideoPrompt: (projectId, shotId, data) => 
    api.post(`/projects/${projectId}/shots/${shotId}/video-prompt`, data),
  // 从视频页面重新生成首帧
  regenerateKeyframe: (projectId, shotId, data = {}) => 
    api.post(`/projects/${projectId}/shots/${shotId}/regenerate-keyframe-from-video`, data),
}

// 队列
export const queueApi = {
  status: () => api.get('/queues/status'),
}

// 提示词配置
export const promptApi = {
  get: () => api.get('/config/prompts'),
  update: (data) => api.put('/config/prompts', data),
}

// 配置导入/导出
export const configApi = {
  export: () => api.get('/config/export'),
  import: (config) => api.post('/config/import', { config }),
}

// API提供商管理
export const providerApi = {
  list: () => api.get('/providers'),
  create: (data) => api.post('/providers', data),
  update: (id, data) => api.put(`/providers/${id}`, data),
  delete: (id) => api.delete(`/providers/${id}`),
  parseCurl: (curlCommand) => api.post('/providers/parse-curl', { curl_command: curlCommand }),
  verify: (id) => api.post(`/providers/${id}/verify`),
  getDefault: (type) => api.get(`/providers/default/${type}`),
  setDefault: (id) => api.post(`/providers/${id}/set-default`),
}

export default api
