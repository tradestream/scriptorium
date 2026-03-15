import * as api from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
  try {
    const [book, progress, user] = await Promise.all([
      api.getBook(params.id),
      api.getReadProgress(params.id).catch(() => null),
      api.getCurrentUser().catch(() => null),
    ]);

    return { book, progress, user };
  } catch (error) {
    console.error('Failed to load book:', error);
    return { book: null, progress: null, user: null };
  }
};
