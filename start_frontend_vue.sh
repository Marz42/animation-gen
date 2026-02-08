#!/bin/bash
# 启动 Vue 3 前端

cd "$(dirname "$0")/frontend"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
fi

echo "🚀 启动 Vue 3 前端..."
npm run dev
