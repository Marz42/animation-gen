import { createRouter, createWebHistory } from 'vue-router'
import Projects from '../views/Projects.vue'
import ScriptParse from '../views/ScriptParse.vue'
import References from '../views/References.vue'
import Shots from '../views/Shots.vue'
import Keyframes from '../views/Keyframes.vue'
import Videos from '../views/Videos.vue'
import Queue from '../views/Queue.vue'
import Settings from '../views/Settings.vue'

const routes = [
  { path: '/', name: 'Projects', component: Projects },
  { path: '/script', name: 'ScriptParse', component: ScriptParse },
  { path: '/references', name: 'References', component: References },
  { path: '/shots', name: 'Shots', component: Shots },
  { path: '/keyframes', name: 'Keyframes', component: Keyframes },
  { path: '/videos', name: 'Videos', component: Videos },
  { path: '/queue', name: 'Queue', component: Queue },
  { path: '/settings', name: 'Settings', component: Settings },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
