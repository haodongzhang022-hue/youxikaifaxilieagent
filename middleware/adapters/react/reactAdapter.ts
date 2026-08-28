/**
 * reactAdapter.ts - React (Web/WASM) 引擎适配器
 * 对齐 Issue #90 wp_engine：Web 端经 Emscripten WASM 调用 C++ 中间件核心。
 *
 * 职责：
 *   1. 将 React 组件/渲染循环接入 middleware C ABI
 *   2. 消费中间件确定性输出（程序化生成/战斗结算/状态机）
 *   3. 提供跨引擎一致的接口，保证 Web 与其他端（Cocos/Unity/UE）行为一致
 */
import {
  GameMiddleware,
  GameState,
  hashJson,
} from "../../bindings/typescript/cabi";

export interface WorldSnapshot {
  terrain: any;
  props: any;
  resources: any;
  tick: number;
  hash: string;
}

/**
 * React 引擎适配器。
 * 将 React 渲染循环与 middleware 确定性核心桥接。
 * Web 端用 WASM 加载 C++ 核心，保证与 Cocos/Unity/UE 输出一致。
 */
export class ReactAdapter {
  readonly engineName = "react-wasm";

  private middleware: GameMiddleware;
  private tick = 0;
  private worldSeed: string;

  constructor(seed = "react_default") {
    this.worldSeed = seed;
    this.middleware = new GameMiddleware();
  }

  /** 初始化引擎 + 中间件 */
  async initialize(): Promise<void> {
    await this.middleware.ready;
    await this.middleware.setState(GameState.PLAYING);
    console.info(`[ReactAdapter] middleware v${await this.middleware.getVersion()}`);
  }

  /** 每帧更新（固定 30Hz Tick，与 combat/numeric 层一致） */
  async frame(deltaSeconds: number): Promise<WorldSnapshot> {
    const dt = deltaSeconds;
    await this.middleware.update(dt);

    // 累加 30Hz tick
    this.tick += 1;

    // 从中间件读取确定性世界数据
    const terrain = await this.middleware.generateTerrain(
      `${this.worldSeed}_${this.tick}`, 8, 8
    );

    return {
      terrain,
      props: null,
      resources: null,
      tick: this.tick,
      hash: hashJson(terrain),
    };
  }

  /** 切换到新世界种子（程序化生成） */
  async switchWorld(seed: string): Promise<void> {
    this.worldSeed = seed;
    this.tick = 0;
  }

  /** 获取当前世界一致性 hash（用于跨引擎比对） */
  async worldHash(seed: string): Promise<string> {
    const terrain = await this.middleware.generateTerrain(seed, 8, 8);
    return hashJson(terrain);
  }
}
