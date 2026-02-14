<template>
  <el-container class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="28" color="#409EFF"><VideoCamera /></el-icon>
        <span class="logo-text">动画生成系统</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        class="nav-menu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/">
          <el-icon><Folder /></el-icon>
          <span>项目管理</span>
        </el-menu-item>
        <el-menu-item index="/script">
          <el-icon><Document /></el-icon>
          <span>剧本解析</span>
        </el-menu-item>
        <el-menu-item index="/references">
          <el-icon><Picture /></el-icon>
          <span>参考图</span>
        </el-menu-item>
        <el-menu-item index="/shots">
          <el-icon><Film /></el-icon>
          <span>分镜设计</span>
        </el-menu-item>
        <el-menu-item index="/keyframes">
          <el-icon><Camera /></el-icon>
          <span>首帧生成</span>
        </el-menu-item>
        <el-menu-item index="/videos">
          <el-icon><VideoPlay /></el-icon>
          <span>视频生成</span>
        </el-menu-item>
        <el-menu-item index="/queue">
          <el-icon><Histogram /></el-icon>
          <span>队列状态</span>
        </el-menu-item>
        <el-menu-item index="/prompts">
          <el-icon><EditPen /></el-icon>
          <span>提示词管理</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <breadcrumb />
        </div>
        <div class="header-right">
          <queue-status />
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import Breadcrumb from './components/Breadcrumb.vue'
import QueueStatus from './components/QueueStatus.vue'
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20px;
  border-bottom: 1px solid #1f2d3d;
}

.logo-text {
  margin-left: 12px;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.nav-menu {
  border-right: none;
}

.header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
