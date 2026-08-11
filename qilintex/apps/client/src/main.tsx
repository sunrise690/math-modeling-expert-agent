import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

// Yjs/Hocuspocus 连接属于外部副作用；开发模式重复挂载会把新文档模板合并两次。
createRoot(document.getElementById('root')!).render(<App />)
