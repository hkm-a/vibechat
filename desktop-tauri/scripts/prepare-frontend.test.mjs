import assert from "node:assert/strict";
import { access, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { prepareFrontend } from "./prepare-frontend.mjs";

async function withTemporaryDirectory(run) {
  const directory = await mkdtemp(join(tmpdir(), "vibechat-frontend-"));

  try {
    await run(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("复制桌面入口并返回目标路径", async () => {
  await withTemporaryDirectory(async (directory) => {
    const source = join(directory, "index.html");
    const destination = join(directory, "dist", "index.html");
    await writeFile(source, "<main>VibeChat</main>", "utf8");

    const result = await prepareFrontend({ source, destination });

    assert.equal(result, destination);
    assert.equal(await readFile(destination, "utf8"), "<main>VibeChat</main>");
  });
});

test("目标目录不存在时自动创建完整目录树", async () => {
  await withTemporaryDirectory(async (directory) => {
    const source = join(directory, "index.html");
    const destination = join(directory, "deep", "dist", "index.html");
    await writeFile(source, "<!doctype html>", "utf8");

    await prepareFrontend({ source, destination });

    await assert.doesNotReject(access(destination));
  });
});

test("源文件缺失时明确失败且不生成目标文件", async () => {
  await withTemporaryDirectory(async (directory) => {
    const destination = join(directory, "dist", "index.html");

    await assert.rejects(
      prepareFrontend({
        source: join(directory, "missing.html"),
        destination,
      }),
      { code: "ENOENT" },
    );
    await assert.rejects(access(destination), { code: "ENOENT" });
  });
});

test("等待页提供通用启动指引并自动探测 Tinode", async () => {
  const page = await readFile(new URL("../index.html", import.meta.url), "utf8");

  assert.match(page, /docker compose up -d/);
  assert.match(page, /fetch\(target/);
  assert.match(page, /location\.replace\(target\)/);
  assert.doesNotMatch(page, /\/home\/[^/]+\/|[A-Z]:\\Users\\/i);
});
