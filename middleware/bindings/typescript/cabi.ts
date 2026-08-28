/**
 * cabi.ts - 跨引擎中间件 TypeScript 绑定（Web/React WASM 层）
 * 对齐 Issue #90 wp_engine：TS 侧经 WASM / Native Plugin 调用 C++ 核心。
 * 注释中标注 C ABI 函数签名，供 Emscripten 自动生成绑定。
 *
 * 确定性契约：同 seed 调用生成器，跨引擎（TS/C#/C++/Python）输出 hash 一致。
 *
 * wp_client 接入：ReactWebAdapter 经本封装统一调用中间件 C ABI。
 */

export enum GameState {
  IDLE = 0,
  PLAYING = 1,
  PAUSED = 2,
  GAMEOVER = 3,
}

/** 程序化生成类型枚举。 */
export type ProcgenType = "terrain" | "level" | "resources" | "props" | "narrative";

/**
 * 跨引擎中间件封装（Web 端经 WASM / Native Plugin）。
 * ReactWebAdapter 经此统一入口调用 C++ 核心逻辑。
 */
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

  /** 将 JS 字符串写入 WASM 堆，返回指针。 */
  private writeString(m: any, str: string): number {
    const bytes = new TextEncoder().encode(str + "\0");
    const ptr = m._malloc(bytes.length);
    m.HEAPU8.set(bytes, ptr);
    return ptr;
  }

  /** 读取 WASM 堆中的 JSON 结果字符串并解析。 */
  private readJsonOut(m: any, outPtr: number): any {
    const jsonPtr = m.HEAPU32[outPtr / 4];
    const jsonStr = m.UTF8ToString(jsonPtr);
    m._cabi_procgen_free_result(jsonPtr); // 释放 C++ 侧分配内存
    return JSON.parse(jsonStr);
  }

  /** 释放多个指针。 */
  private freePtrs(m: any, ptrs: number[]): void {
    for (const p of ptrs) {
      if (p) m._free(p);
    }
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
  /** 地形生成。C ABI: cabi_procgen_terrain(seed, w, h, params_json, &out_json) */
  async generateTerrain(seed: string, width = 8, height = 8): Promise<any> {
    const m = await this.mod();
    const seedPtr = this.writeString(m, seed);
    const paramsPtr = this.writeString(m, "{}");
    const outPtr = m._malloc(8);
    m._cabi_procgen_terrain(seedPtr, width, height, paramsPtr, outPtr);
    const result = this.readJsonOut(m, outPtr);
    this.freePtrs(m, [seedPtr, paramsPtr, outPtr]);
    return result;
  }

  /** 关卡生成。C ABI: cabi_procgen_level(seed, level_params, &out_json) */
  async generateLevel(seed: string, params: object = {}): Promise<any> {
    const m = await this.mod();
    const seedPtr = this.writeString(m, seed);
    const paramsPtr = this.writeString(m, JSON.stringify(params));
    const outPtr = m._malloc(8);
    m._cabi_procgen_level(seedPtr, paramsPtr, outPtr);
    const result = this.readJsonOut(m, outPtr);
    this.freePtrs(m, [seedPtr, paramsPtr, outPtr]);
    return result;
  }

  /** 资源分布生成。C ABI: cabi_procgen_resources(seed, terrain_data, rules_json, &out_json) */
  async generateResources(seed: string, terrainData: object = {}, rules: object = {}): Promise<any> {
    const m = await this.mod();
    const seedPtr = this.writeString(m, seed);
    const terrainPtr = this.writeString(m, JSON.stringify(terrainData));
    const rulesPtr = this.writeString(m, JSON.stringify(rules));
    const outPtr = m._malloc(8);
    m._cabi_procgen_resources(seedPtr, terrainPtr, rulesPtr, outPtr);
    const result = this.readJsonOut(m, outPtr);
    this.freePtrs(m, [seedPtr, terrainPtr, rulesPtr, outPtr]);
    return result;
  }

  /** 装饰物生成。C ABI: cabi_procgen_props(seed, params_json, &out_json) */
  async generateProps(seed: string, params: object = {}): Promise<any> {
    const m = await this.mod();
    const seedPtr = this.writeString(m, seed);
    const paramsPtr = this.writeString(m, JSON.stringify(params));
    const outPtr = m._malloc(8);
    m._cabi_procgen_props(seedPtr, paramsPtr, outPtr);
    const result = this.readJsonOut(m, outPtr);
    this.freePtrs(m, [seedPtr, paramsPtr, outPtr]);
    return result;
  }

  /** 叙事生成。C ABI: cabi_procgen_narrative(seed, narrative_schema, &out_json) */
  async generateNarrative(seed: string, schema: object = {}): Promise<any> {
    const m = await this.mod();
    const seedPtr = this.writeString(m, seed);
    const schemaPtr = this.writeString(m, JSON.stringify(schema));
    const outPtr = m._malloc(8);
    m._cabi_procgen_narrative(seedPtr, schemaPtr, outPtr);
    const result = this.readJsonOut(m, outPtr);
    this.freePtrs(m, [seedPtr, schemaPtr, outPtr]);
    return result;
  }

  // ---- 战斗 ----
  /** 计算伤害。C ABI: cabi_combat_calc_damage(...) */
  async calcDamage(skillConfig: object, attackerStats: object, targetStats: object): Promise<number> {
    const m = await this.mod();
    const skillPtr = this.writeString(m, JSON.stringify(skillConfig));
    const atkPtr = this.writeString(m, JSON.stringify(attackerStats));
    const tgtPtr = this.writeString(m, JSON.stringify(targetStats));
    const outPtr = m._malloc(8);
    m._cabi_combat_calc_damage(skillPtr, atkPtr, tgtPtr, outPtr);
    const damage = m.HEAPU32[outPtr / 4];
    this.freePtrs(m, [skillPtr, atkPtr, tgtPtr, outPtr]);
    return damage;
  }
}

/**
 * 一致性 SHA-256 hash（用于跨引擎 golden hash 比对）。
 * 与 Python hashlib.sha256 / C++ 侧 sha256 输出一致。
 * 纯 JS 实现兜底（不依赖浏览器/Node crypto API）。
 */
export async function hashJson(obj: unknown): Promise<string> {
  const str = JSON.stringify(obj, Object.keys(obj as any).sort());
  const utf8 = new TextEncoder().encode(str);

  // 优先使用 Web Crypto API（浏览器/Node 均可用）
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", utf8);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // 纯 JS SHA-256 实现兜底
  return sha256Hex(utf8);
}

/** 纯 JS SHA-256 实现（字节数组输入）。 */
function sha256Hex(bytes: Uint8Array): string {
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b,
    0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7,
    0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152,
    0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
    0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
    0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];

  const H = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];

  const l = bytes.length;
  const bitLen = l * 8;
  const padded = new Uint8Array(((l + 8) >> 6 << 6) + 64);
  padded.set(bytes);
  padded[l] = 0x80;
  const dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000));
  dv.setUint32(padded.length - 4, bitLen >>> 0);

  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n));

  for (let i = 0; i < padded.length; i += 64) {
    const w = new Array<number>(64);
    for (let j = 0; j < 16; j++) w[j] = dv.getUint32(i + j * 4);
    for (let j = 16; j < 64; j++) {
      const s0 = rotr(w[j - 15], 7) ^ rotr(w[j - 15], 18) ^ (w[j - 15] >>> 3);
      const s1 = rotr(w[j - 2], 17) ^ rotr(w[j - 2], 19) ^ (w[j - 2] >>> 10);
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let j = 0; j < 64; j++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K[j] + w[j]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e;
      e = (d + temp1) >>> 0;
      d = c; c = b; b = a;
      a = (temp1 + temp2) >>> 0;
    }
    H[0] = (H[0] + a) >>> 0; H[1] = (H[1] + b) >>> 0;
    H[2] = (H[2] + c) >>> 0; H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0; H[5] = (H[5] + f) >>> 0;
    H[6] = (H[6] + g) >>> 0; H[7] = (H[7] + h) >>> 0;
  }

  return H.map((x) => (x >>> 0).toString(16).padStart(8, "0")).join("");
}
