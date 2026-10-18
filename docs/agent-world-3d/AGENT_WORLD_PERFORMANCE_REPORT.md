# Agent World performance report

## Implemented controls

- One shared Three.js scene/material setup; low-poly procedural geometry and generated local labels.
- Device pixel ratio is capped at 1.4.
- Animation loop draws at most about 30 frames per second, and only while the view is visible and selected.
- Polling changes update object state rather than reconstructing the DOM/scene.
- Camera damping is disabled when `prefers-reduced-motion` is enabled.
- Controls, resize observers, event handlers, geometry, material maps/materials, renderer and WebGL context have disposal paths.
- WebGL2 context-loss handlers suspend rendering and offer the 2D Fleet view.

## Measurements

Chrome 155 headless rendered the scene with ANGLE/Vulkan SwiftShader at 1600×1100 and created the canvas successfully. This is a software renderer. No defensible RTX 3060 Ti FPS, GPU utilization or VRAM measurement was produced. WebGL resource counters are not exposed to the application and no long-session heap/VRAM sampling was run. Accordingly, target-GPU smoothness and memory-stability acceptance are NOT_EXECUTED; they must be measured in an interactive Windows Chrome/Edge session on the target machine.
