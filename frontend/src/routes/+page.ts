import * as api from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
  const [statsResult, recentResult] = await Promise.allSettled([
    api.getReadingStats(),
    api.getBooks({ limit: 18 }),
  ]);

  const stats = statsResult.status === 'fulfilled' ? statsResult.value : null;
  const recent = recentResult.status === 'fulfilled' ? recentResult.value.items : [];

  return { stats, recent };
};
