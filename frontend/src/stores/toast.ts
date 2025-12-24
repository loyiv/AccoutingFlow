import { defineStore } from 'pinia'

export type ToastKind = 'success' | 'info' | 'warning' | 'error'

type ToastState = {
  visible: boolean
  text: string
  kind: ToastKind
  delayMs: number
  durationMs: number
  scale: number
  _timer1?: number
  _timer2?: number
}

export const useToastStore = defineStore('toast', {
  state: (): ToastState => ({
    visible: false,
    text: '',
    kind: 'success',
    delayMs: 0,
    durationMs: 1000,
    scale: 3, // 默认比之前大 3 倍
    _timer1: undefined,
    _timer2: undefined,
  }),
  actions: {
    hide() {
      if (this._timer1) window.clearTimeout(this._timer1)
      if (this._timer2) window.clearTimeout(this._timer2)
      this._timer1 = undefined
      this._timer2 = undefined
      this.visible = false
    },
    show(text: string, opts?: Partial<Pick<ToastState, 'kind' | 'delayMs' | 'durationMs' | 'scale'>>) {
      this.hide()
      this.text = text
      this.kind = opts?.kind || 'success'
      this.delayMs = typeof opts?.delayMs === 'number' ? opts.delayMs : 0
      this.durationMs = typeof opts?.durationMs === 'number' ? opts.durationMs : 1000
      this.scale = typeof opts?.scale === 'number' ? opts.scale : 3

      this._timer1 = window.setTimeout(() => {
        this.visible = true
        this._timer2 = window.setTimeout(() => {
          this.visible = false
        }, this.durationMs)
      }, this.delayMs)
    },
    success(text: string, opts?: Partial<Pick<ToastState, 'delayMs' | 'durationMs' | 'scale'>>) {
      this.show(text, { ...opts, kind: 'success' })
    },
  },
})


