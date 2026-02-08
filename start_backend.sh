#!/bin/bash

# 单独启动后端（用于测试）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "🚀 启动后端API..."
echo "访问: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""

# 在项目根目录启动，确保路径正确
# 使用导入字符串形式启动以支持 reload
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
