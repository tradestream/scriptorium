/**
 * Minimal toast notification store.
 * Components subscribe to `toasts` and call `addToast` to show a message.
 */

export type ToastVariant = 'default' | 'success' | 'error';

export interface Toast {
  id: number;
  message: string;
  variant: ToastVariant;
}

let _id = 0;

function createToastStore() {
  let items = $state<Toast[]>([]);

  function add(message: string, variant: ToastVariant = 'default', durationMs = 4000) {
    const id = ++_id;
    items = [...items, { id, message, variant }];
    setTimeout(() => remove(id), durationMs);
  }

  function remove(id: number) {
    items = items.filter((t) => t.id !== id);
  }

  return {
    get items() {
      return items;
    },
    add,
    remove,
  };
}

export const toastStore = createToastStore();
