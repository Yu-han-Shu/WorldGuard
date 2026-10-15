import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { mergeCells, pathSample } from "./src/mapGeometry.ts";

test("all catalog visuals preserve exact occupied cells without filling doorways", () => {
  const scenes = JSON.parse(
    readFileSync(new URL("./src/data/scenes.json", import.meta.url), "utf8"),
  );
  for (const { scene } of Object.values(scenes) as any[]) {
    const reconstructed: string[] = [];
    for (const b of mergeCells(scene.occupied)) {
      for (let row = b.row; row < b.row + b.height; row++)
        for (let col = b.col; col < b.col + b.width; col++)
          reconstructed.push(`${row},${col}`);
    }
    assert.equal(
      reconstructed.length,
      new Set(reconstructed).size,
      scene.scene_id,
    );
    assert.deepEqual(
      new Set(reconstructed),
      new Set(scene.occupied.map((c: number[]) => c.join(","))),
      scene.scene_id,
    );
  }
});

test("path playback follows travelled distance, handles repeated points and clamps endpoints", () => {
  const path = [
    [0, 0],
    [0, 0],
    [3, 0],
    [3, 4],
  ];
  assert.deepEqual(pathSample(path, 0.5).point, [3, 0.5]);
  assert.equal(pathSample(path, 0.5).angle, 90);
  assert.equal(pathSample(path, 0.5).total, 7);
  assert.deepEqual(pathSample(path, -1).point, [0, 0]);
  assert.deepEqual(pathSample(path, 2).point, [3, 4]);
  assert.deepEqual(pathSample([[2, 1]], 0.8).point, [2, 1]);
  assert.deepEqual(pathSample([], 0).point, []);
});
