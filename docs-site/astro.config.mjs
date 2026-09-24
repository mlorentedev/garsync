import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://mlorentedev.github.io',
  base: '/garsync',
  integrations: [
    starlight({
      title: 'GarSync',
      // Starlight >= 0.33 wants an array of link items here; the object form was
      // removed and build-time rejects it. This was the docs build's failure on
      // master from 2026-08-11 to 2026-09-25 (CI-002), invisible because the
      // workflow had no pull_request trigger: the red run only ever appeared
      // AFTER the dependabot bump had already landed.
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/mlorentedev/garsync' },
      ],
      head: [
        {
          tag: 'meta',
          attrs: { name: 'theme-color', content: '#0ea5e9' },
        },
        {
          tag: 'script',
          attrs: { type: 'application/ld+json' },
          content: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            name: 'GarSync',
            description: 'Personal fitness data pipeline from Garmin Connect to local SQLite.',
            applicationCategory: 'HealthApplication',
            operatingSystem: 'Cross-platform',
            url: 'https://mlorentedev.github.io/garsync/',
            license: 'https://opensource.org/licenses/MIT',
          }),
        },
      ],
      sidebar: [
        {
          label: 'Getting Started',
          items: [
            { label: 'Introduction', slug: 'introduction' },
            { label: 'Quick Setup', slug: 'getting-started' },
          ],
        },
        {
          label: 'Deployment',
          items: [
            { label: 'Self-Hosted Guide', slug: 'deploy/self-hosted' },
            { label: 'Docker Compose', slug: 'deploy/docker' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'API Endpoints', slug: 'reference/api' },
            { label: 'CLI Commands', slug: 'reference/cli' },
          ],
        },
      ],
      customCss: ['./src/styles/custom.css'],
    }),
  ],
});
