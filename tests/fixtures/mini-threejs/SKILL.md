---
name: mini-threejs
description: "生成基础 Three.js 3D 网页场景。当用户需要创建简单的 3D 几何体展示或基础 Three.js 网页时使用。"
---

# Mini Three.js 场景生成（基线测试夹具）

> 本文件是 `pangu-create` 测试集 `test-prompts.json` 第 2 题（进化流 E0-E3）的自包含待升级夹具，模拟一个尚未经过盘古精炼的早期 3D 技能。

## 工作流

1. 创建 HTML 骨架并引入 Three.js CDN。
2. 初始化 `Scene`、`PerspectiveCamera(75, innerWidth/innerHeight, 0.1, 1000)` 与 `WebGLRenderer()`。
3. 添加 `AmbientLight(0xffffff, 1.0)` 与基础几何体（`BoxGeometry` / `SphereGeometry` + `MeshStandardMaterial`）。
4. 在 `requestAnimationFrame` 循环中旋转物体并调用 `renderer.render(scene, camera)`。

## 已知痛点（供盘古 E0-E3 进化轮定位与精炼）

- 光照只有均匀环境光，无主辅光比、无阴影投射、无色调映射（`ACESFilmicToneMapping`），物体呈现塑料悬浮感。
- 缺少 `devicePixelRatio` 限制与窗口 `resize` 自适应。
- 缺少纹理/模型加载失败降级与 WebGL 上下文丢失（`webglcontextlost`）处理。
