#!/bin/bash
# 一键启动脚本 - Gradio版本

cd "$(dirname "$0")"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 启动后端
echo "🚀 启动后端服务 (FastAPI @ :8000)..."
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动Gradio前端
echo "🎨 启动Gradio前端 (:7860)..."
python src/app_gradio.py &
FRONTEND_PID=$!

echo ""
echo "✅ 服务已启动!"
echo "📱 Gradio前端: http://localhost:7860"
echo "🔌 API后端: http://localhost:8000"
echo "📚 API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获信号，优雅关闭
trap "echo ''; echo '🛑 停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# 等待
wait
