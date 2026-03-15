import { getShelf, getShelfBooks } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
  try {
    const [shelf, books] = await Promise.all([
      getShelf(params.id),
      getShelfBooks(params.id),
    ]);
    return { shelf, books };
  } catch {
    return { shelf: null, books: [] };
  }
};
