import { defineStore } from 'pinia'
import { api } from '../services/api'

export type Book = { id: string; name: string; base_currency_id: string }
export type Period = { id: string; book_id: string; year: number; month: number; status: string }

export const useAppStore = defineStore('app', {
  state: () => ({
    books: [] as Book[],
    periods: [] as Period[],
    selectedBookId: '',
    selectedPeriodId: '',
  }),
  getters: {
    selectedBook(state): Book | null {
      return state.books.find((b) => b.id === state.selectedBookId) || null
    },
    selectedBookName(): string {
      return this.selectedBook?.name || (this.selectedBookId ? '（未加载账簿名称）' : '—')
    },
    selectedPeriod(state): Period | null {
      return state.periods.find((p) => p.id === state.selectedPeriodId) || null
    },
    selectedPeriodLabel(): string {
      const p = this.selectedPeriod
      if (!p) return this.selectedPeriodId ? '（未加载期间）' : '—'
      return `${p.year}-${String(p.month).padStart(2, '0')}（${p.status}）`
    },
  },
  actions: {
    async init() {
      this.books = await api.listBooks()
      if (!this.selectedBookId && this.books.length) this.selectedBookId = this.books[0].id
      if (this.selectedBookId) {
        this.periods = await api.listPeriods(this.selectedBookId)
        if (!this.selectedPeriodId && this.periods.length) this.selectedPeriodId = this.periods[0].id
      }
    },
    async reloadPeriods() {
      if (!this.selectedBookId) return
      this.periods = await api.listPeriods(this.selectedBookId)
      if (!this.selectedPeriodId && this.periods.length) this.selectedPeriodId = this.periods[0].id
    },
  },
})


