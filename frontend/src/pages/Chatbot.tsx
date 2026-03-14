import { motion } from 'framer-motion'
import ChatbotPanel from '../components/chatbot/ChatbotPanel'

export default function Chatbot() {
  return (
    <div className="page-shell full-height">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}
      >
        <ChatbotPanel />
      </motion.div>
    </div>
  )
}
