import { defineCollection } from 'astro:content';
// Astro 5's content layer requires an explicit loader: without `docsLoader()` the
// docs collection has no entries, and every sidebar slug resolves to "does not
// exist". Legacy form: defineCollection({ schema: docsSchema() }) — the shape this
// file carried until the docs build was repaired (CI-002, broken on master
// 2026-08-11 → 2026-09-25).
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
	docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
