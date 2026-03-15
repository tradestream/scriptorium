import * as api from '$lib/api/client';

export async function load() {
  const [authors, tags, series] = await Promise.allSettled([
    api.getAuthors(0, 2000),
    api.getTags(0, 2000),
    api.getAllSeries(0, 2000),
  ]);
  return {
    authors: authors.status === 'fulfilled' ? authors.value : [],
    tags: tags.status === 'fulfilled' ? tags.value : [],
    series: series.status === 'fulfilled' ? series.value : [],
  };
}
