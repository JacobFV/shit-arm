import { useEffect, useState, useRef, useCallback } from "react"
import { ArmWebSocketClient } from "./client"
import type { ArmState, Command } from "./types"

export function useArmWebSocket(url: string) {
  const [state, setState] = useState<ArmState | null>(null)
  const [connected, setConnected] = useState(false)
  const clientRef = useRef<ArmWebSocketClient | null>(null)

  useEffect(() => {
    const client = new ArmWebSocketClient(url)
    clientRef.current = client

    const unsubState = client.onState(setState)
    const unsubConn = client.onConnectionChange(setConnected)

    client.connect()

    return () => {
      unsubState()
      unsubConn()
      client.disconnect()
      clientRef.current = null
    }
  }, [url])

  const sendCommand = useCallback((cmd: Command) => {
    clientRef.current?.sendCommand(cmd)
  }, [])

  return { state, connected, sendCommand }
}
