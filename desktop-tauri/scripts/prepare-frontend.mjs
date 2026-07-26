import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const desktopDirectory = resolve(scriptDirectory, "..");

export async function prepareFrontend({
  source = resolve(desktopDirectory, "index.html"),
  destination = resolve(desktopDirectory, "dist", "index.html"),
} = {}) {
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(source, destination);
  return destination;
}

const entryPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";

if (import.meta.url === entryPath) {
  const destination = await prepareFrontend();
  console.log(`已准备桌面前端：${destination}`);
}
