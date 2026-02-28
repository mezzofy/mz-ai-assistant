import {WS_BASE_URL} from '../config';
import {getAccessToken} from '../storage/tokenStorage';
import type {ChatResponse} from './chat';

// ── Inbound message types (Server → Client) ───────────────────────────────────
// Matches format_ws_message() in server/app/output/output_formatter.py

export type WsInboundMessage =
  | {type: 'status'; message: string}
  | {type: 'transcript'; text: string; is_final: boolean}
  | {type: 'camera_analysis'; description: string}
  | {type: 'complete'; response: ChatResponse}
  | {type: 'error'; detail: string};

export type WsCallbacks = {
  onStatus?: (message: string) => void;
  onTranscript?: (text: string, isFinal: boolean) => void;
  onCameraAnalysis?: (description: string) => void;
  onComplete?: (response: ChatResponse) => void;
  onError?: (detail: string) => void;
  onDisconnect?: () => void;
};

// ── MzWebSocket ───────────────────────────────────────────────────────────────

export class MzWebSocket {
  private ws: WebSocket | null = null;
  private callbacks: WsCallbacks = {};

  async connect(callbacks: WsCallbacks): Promise<void> {
    this.callbacks = callbacks;

    const token = await getAccessToken();
    if (!token) {
      throw new Error('No access token — cannot open WebSocket');
    }

    const url = `${WS_BASE_URL}/chat/ws?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onmessage = event => {
      try {
        const msg = JSON.parse(event.data as string) as WsInboundMessage;
        this._handleMessage(msg);
      } catch {
        // Ignore unparseable frames
      }
    };

    this.ws.onerror = () => {
      this.callbacks.onError?.('WebSocket connection error');
    };

    this.ws.onclose = () => {
      this.callbacks.onDisconnect?.();
    };

    // Wait for connection to open (or timeout after 10s)
    await new Promise<void>((resolve, reject) => {
      if (!this.ws) {
        reject(new Error('WebSocket not initialised'));
        return;
      }
      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timed out'));
      }, 10_000);
      this.ws.onopen = () => {
        clearTimeout(timeout);
        resolve();
      };
    });
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // ── Client → Server messages ──────────────────────────────────────────────
  // Matches message types in server/app/api/chat.py WebSocket handler

  sendSpeechStart(): void {
    this._send({type: 'speech_start'});
  }

  sendSpeechAudio(base64Chunk: string): void {
    this._send({type: 'speech_audio', data: base64Chunk});
  }

  sendSpeechEnd(sessionId?: string | null): void {
    this._send({type: 'speech_end', ...(sessionId ? {session_id: sessionId} : {})});
  }

  sendCameraFrame(base64Jpeg: string): void {
    this._send({type: 'camera_frame', data: base64Jpeg});
  }

  sendText(message: string, sessionId?: string | null): void {
    this._send({
      type: 'text',
      message,
      ...(sessionId ? {session_id: sessionId} : {}),
    });
  }

  // ── Internals ─────────────────────────────────────────────────────────────

  private _send(data: object): void {
    if (!this.isConnected) {
      return; // Silently drop — caller checks isConnected if needed
    }
    this.ws!.send(JSON.stringify(data));
  }

  private _handleMessage(msg: WsInboundMessage): void {
    switch (msg.type) {
      case 'status':
        this.callbacks.onStatus?.(msg.message);
        break;
      case 'transcript':
        this.callbacks.onTranscript?.(msg.text, msg.is_final);
        break;
      case 'camera_analysis':
        this.callbacks.onCameraAnalysis?.(msg.description);
        break;
      case 'complete':
        this.callbacks.onComplete?.(msg.response);
        break;
      case 'error':
        this.callbacks.onError?.(msg.detail);
        break;
    }
  }
}

// Singleton WS instance — shared across ChatScreen and CameraScreen
export const mzWs = new MzWebSocket();
