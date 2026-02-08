import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useProjectStore = defineStore('project', () => {
  // State
  const currentProject = ref(null)
  const projects = ref([])
  const loading = ref(false)

  // Getters
  const hasProject = computed(() => !!currentProject.value)
  const projectId = computed(() => currentProject.value?.project_id)

  // Actions
  const setCurrentProject = (project) => {
    currentProject.value = project
  }

  const setProjects = (list) => {
    projects.value = list
  }

  const clearProject = () => {
    currentProject.value = null
  }

  return {
    currentProject,
    projects,
    loading,
    hasProject,
    projectId,
    setCurrentProject,
    setProjects,
    clearProject,
  }
})
