import { defineStore } from 'pinia'
import { api } from '../services/api'

export type Me = { id: string; username: string; role: string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    me: null as Me | null,
  }),
  getters: {
    isAuthed: (s) => !!s.token,
  },
  actions: {
    async login(username: string, password: string) {
      const t = await api.login(username, password)
      this.token = t
      localStorage.setItem('token', t)
      this.me = await api.me()
    },
    async loadMe() {
      if (!this.token) return
      this.me = await api.me()
    },
    logout() {
      this.token = ''
      this.me = null
      localStorage.removeItem('token')
    },
  },
})


