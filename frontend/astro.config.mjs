// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@astrojs/tailwind";

export default defineConfig({
  integrations: [tailwindcss()],
  server: { port: 4321 },
});
