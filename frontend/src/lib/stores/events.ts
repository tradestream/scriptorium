/**
 * WebSocket event client.
 *
 * Connects to /ws/events and dispatches typed server-sent events.
 * Reconnects automatically with exponential back-off.
 */

import { getAuthToken, getServerUrl } from '$lib/api/client';
import { toastStore } from './toasts.svelte';

type ServerEvent =
  | { type: 'book_added'; data: { id: number; title: string; library_id: number } }
  | { type: 'ingest_progress'; data: { filename: string; status: string; book_id: number | null } }
  | { type: 'library_scan_done'; data: { library_id: number; added: number; updated: number } };

let ws: WebSocket | null = null;
let retryDelay = 1000;
let stopped = false;

function wsUrl(): string {
  const token = getAuthToken();
  const serverUrl = getServerUrl();
  let base: string;
  if (serverUrl) {
    // Native / Capacitor: build absolute WS URL from the stored server URL
    const wsProto = serverUrl.startsWith('https') ? 'wss' : 'ws';
    base = `${wsProto}://${serverUrl.replace(/^https?:\/\//, '')}/ws/events`;
  } else {
    // Web: use current host
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    base = `${proto}://${location.host}/ws/events`;
  }
  return token ? `${base}?token=${token}` : base;
}

function handleEvent(evt: ServerEvent) {
  switch (evt.type) {
    case 'book_added':
      toastStore.add(`"${evt.data.title}" added to library`, 'success');
      break;
    case 'ingest_progress':
      if (evt.data.status === 'imported') {
        toastStore.add(`Imported: ${evt.data.filename}`, 'success');
      } else if (evt.data.status === 'error') {
        toastStore.add(`Ingest failed: ${evt.data.filename}`, 'error');
      }
      break;
    case 'library_scan_done':
      toastStore.add(
        `Library scan complete — ${evt.data.added} added, ${evt.data.updated} updated`,
        'default',
      );
      break;
  }
}

function connect() {
  if (stopped) return;

  try {
    ws = new WebSocket(wsUrl());
  } catch {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    retryDelay = 1000;
  };

  ws.onmessage = (msg) => {
    try {
      const evt = JSON.parse(msg.data) as ServerEvent;
      handleEvent(evt);
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = () => {
    ws = null;
    scheduleReconnect();
  };

  ws.onerror = () => {
    ws?.close();
  };
}

function scheduleReconnect() {
  if (stopped) return;
  setTimeout(() => connect(), retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30_000);
}

export function startEventClient() {
  stopped = false;
  connect();
}

export function stopEventClient() {
  stopped = true;
  ws?.close();
  ws = null;
}
