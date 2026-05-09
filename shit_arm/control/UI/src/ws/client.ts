import type { ArmState, Command, WsMessage } from "./types"

export type StateListener = (state: ArmState) => void
export type ConnectionListener = (connected: boolean) => void

export class ArmWebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private stateListeners = new Set<StateListener>()
  private connectionListeners = new Set<ConnectionListener>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private _connected = false
  private destroyed = false

  constructor(url: string) {
    this.url = url
  }

  get connected(): boolean {
    return this._connected
  }

  connect(): void {
    if (this.destroyed) return
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      this._connected = true
      for (const cb of this.connectionListeners) cb(true)
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        if (msg.type === "state") {
          for (const cb of this.stateListeners) cb(msg)
        }
      } catch {
        // ignore parse errors
      }
    }

    this.ws.onclose = () => {
      this._connected = false
      for (const cb of this.connectionListeners) cb(false)
      if (!this.destroyed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000)
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  disconnect(): void {
    this.destroyed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
    this._connected = false
    this.stateListeners.clear()
    this.connectionListeners.clear()
  }

  sendCommand(cmd: Command): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cmd))
    }
  }

  onState(listener: StateListener): () => void {
    this.stateListeners.add(listener)
    return () => this.stateListeners.delete(listener)
  }

  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener)
    return () => this.connectionListeners.delete(listener)
  }
}
