import { getBook } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
  try {
    const book = await getBook(params.id);
    return { book };
  } catch {
    return { book: null };
  }
};
