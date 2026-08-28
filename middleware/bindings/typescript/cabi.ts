/**
 * cabi.ts - 跨引擎中间件 TypeScript 绑定（Web/React WASM 层）
 * 对齐 Issue #90 wp_engine：TS 侧经 WASM / Native Plugin 调用 C++ 核心。
 * 注释中标注 C ABI 函数签名，供 Emscripten 自动生成绑定。
 *
 * 确定性契约：同 seed 调用生成器，跨引擎（TS/C#/C++/Python）输出 hash 一致。
 */

export enum GameState {
  IDLE = 0,
  PLAYING = 1,
  PAUSED = 2,
  GAMEOVER = 3,
}

/** 跨引擎中间件封装（Web 端经 WASM）。 */
export class GameMiddleware {
  private module: any;
  private ready: Promise<void>;

  constructor() {
    // 经 Emscripten 加载 C++ 编译的 WASM 产物（libgame_middleware.wasm）
    this.ready = (async () => {
      // @ts-ignore 生产环境通过 import 加载真实 wasm_module
      const createModule = (await import("./wasm_module")).default;
      this.module = await createModule();
      this.module._cabi_init(null);
    })();
  }

  private async mod() {
    await this.ready;
    return this.module;
  }

  // ---- 玩法状态机 ----
  async setState(state: GameState): Promise<number> {
    const m = await this.mod();
    return m._cabi_gameplay_set_state(state);
  }

  async getState(): Promise<number> {
    const m = await this.mod();
    const ptr = m._malloc(4);
    m._cabi_gameplay_get_state(ptr);
    const state = m.HEAP32[ptr / 4];
    m._free(ptr);
    return state;
  }

  async update(dt: number): Promise<void> {
    const m = await this.mod();
    m._cabi_gameplay_update(dt);
  }

  // ---- 程序化生成（确定性） ----
  // C ABI: int cabi_procgen_terrain(seed, w, h, params_json, &out_json)
  async generateTerrain(seed: string, width = 8, height = 8): Promise<any> {
    const m = await this.mod();
    const seedPtr = m._malloc(seed.length + 1);
    m.HEAPU8.set(new TextEncoder().encode(seed + "\0"), seedPtr);
    const params = m._malloc(1); // {}
    const outPtr = m._malloc(8);
    m._cabi_procgen_terrain(seedPtr, width, height, params, outPtr);
    const jsonPtr = m.HEAPU32[outPtr / 4];
    const jsonStr = m.UTF8ToString(jsonPtr);
    m._free(seedPtr); m._free(params); m._free(outPtr);
    return JSON.parse(jsonStr);
  }
}

/** 一致性 hash（用于跨引擎比对）。 */
export function hashJson(obj: unknown): string {
  const str = JSON.stringify(obj, Object.keys(obj as any).sort());
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}
