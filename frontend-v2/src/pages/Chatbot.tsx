import { motion } from 'framer-motion'
import ChatbotPanel from '../components/Chatbot/ChatbotPanel'

export default function Chatbot() {
  return (
    <div className="page-shell">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
        style={{ height: '100%' }}
      >
        <ChatbotPanel />
      </motion.div>
    </div>
  )
}
