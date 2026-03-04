import { useCallback, useState } from 'react'
import type { DashboardItem } from '../types'

const DASHBOARD_STORAGE_KEY = 'sai_dashboard_items_v1'
const MAX_DASHBOARD_ITEMS = 100

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `dash_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function readStoredItems(): DashboardItem[] {
  if (typeof window === 'undefined') return []

  try {
    const raw = window.localStorage.getItem(DASHBOARD_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as DashboardItem[]
    if (!Array.isArray(parsed)) return []

    return parsed.filter((item): item is DashboardItem => {
      return Boolean(item && item.id && item.title && item.source && item.route && item.savedAt)
    })
  } catch {
    return []
  }
}

function persistItems(items: DashboardItem[]) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(items))
}

export type NewDashboardItem = Omit<DashboardItem, 'id' | 'savedAt'>

export function useDashboard() {
  const [items, setItems] = useState<DashboardItem[]>(() => readStoredItems())

  const addItem = useCallback((input: NewDashboardItem) => {
    setItems(prev => {
      const next: DashboardItem = {
        ...input,
        id: generateId(),
        savedAt: new Date().toISOString(),
      }
      const merged = [next, ...prev].slice(0, MAX_DASHBOARD_ITEMS)
      persistItems(merged)
      return merged
    })
  }, [])

  const removeItem = useCallback((id: string) => {
    setItems(prev => {
      const merged = prev.filter(item => item.id !== id)
      persistItems(merged)
      return merged
    })
  }, [])

  const clearAll = useCallback(() => {
    setItems([])
    persistItems([])
  }, [])

  return {
    items,
    addItem,
    removeItem,
    clearAll,
  }
}
