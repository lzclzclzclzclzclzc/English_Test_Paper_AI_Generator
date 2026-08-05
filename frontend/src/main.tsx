import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { preloadVoices } from './lib/tts'

// 预加载 TTS 语音列表
preloadVoices()

// 阅读外观（设置页可切换）：渲染前应用，避免闪白/闪黑
if (localStorage.getItem('theme') === 'dark') {
  document.documentElement.classList.add('dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
