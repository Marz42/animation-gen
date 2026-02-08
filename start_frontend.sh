#!/bin/bash
# 单独启动Gradio前端

cd "$(dirname "$0")"
source venv/bin/activate

echo "🎨 启动Gradio前端 (:7860)..."
python src/app_gradio.py
