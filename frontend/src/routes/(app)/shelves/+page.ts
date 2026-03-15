import * as api from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
  try {
    const shelves = await api.getShelves();
    return { shelves };
  } catch (error) {
    console.error('Failed to load shelves:', error);
    return { shelves: [] };
  }
};
