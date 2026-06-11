import { mkdir } from "node:fs/promises";
import sharp from "sharp";

await mkdir("public/icons", { recursive: true });

for (const size of [192, 512, 180]) {
  const name = size === 180 ? "apple-touch-icon.png" : `icon-${size}.png`;
  const out = size === 180 ? `public/${name}` : `public/icons/${name}`;
  await sharp("public/favicon.svg").resize(size, size).png().toFile(out);
  console.log("wrote", out);
}
