import { cpSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  publicDir: false,
  plugins: [
    {
      name: "copy-classic-scripts",
      closeBundle() {
        mkdirSync(resolve(root, "dist/src"), { recursive: true });
        cpSync(resolve(root, "src/js"), resolve(root, "dist/src/js"), {
          recursive: true,
        });
      },
    },
  ],
  build: {
    rollupOptions: {
      input: {
        main: resolve(root, "index.html"),
        login: resolve(root, "src/pages/login.html"),
        admin: resolve(root, "src/pages/admin.html"),
        exam: resolve(root, "src/pages/exam.html"),
      },
    },
  },
});
