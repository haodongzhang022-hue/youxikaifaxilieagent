/**
 * cocosAdapter.ts - Cocos (Native Plugin / FFI) 引擎适配器
 * 对齐 Issue #90 wp_engine：Cocos 小程序平台经 Native Plugin FFI 调用 C++ 核心。
 *
 * 职责：
 *   1. 将 Cocos 场景/UI 渲染接入 middleware C ABI
 *   2. TS 侧经 Native FFI 调用 C++（与 React WASM 调用同一核心）
 *   3. 保证 Cocos 小程序与 Web/Unity/UE 输出一致（同 seed 同 hash）
 */
import { GameMiddleware, GameState } from "../../bindings/typescript/cabi";

export interface CocosInitOptions {
  seed?: string;
  viewWidth?: number;
  viewHeight?: number;
  useNative?: boolean;
}

/**
 * Cocos 引擎适配器。
 * 小程序平台侧重轻量与快速分享，渲染用 Cocos Creator，逻辑走 middleware。
 */
export class CocosAdapter {
  readonly engineName = "cocos-native";

  private middleware: GameMiddleware;
  private worldSeed: string;
  private viewWidth: number;
  private viewHeight: number;
  private tick = 0;

  constructor(opts: CocosInitOptions = {}) {
    this.worldSeed = opts.seed ?? "cocos_default";
    this.viewWidth = opts.viewWidth ?? 720;
    this.viewHeight = opts.viewHeight ?? 1280;
    this.middleware = new GameMiddleware();
  }

  /** 初始化 Cocos 场景 + middleware */
  async initialize(): Promise<void> {
    await this.middleware.ready;
    await this.middleware.setState(GameState.PLAYING);
    console.info(`[CocosAdapter] view ${this.viewWidth}x${this.viewHeight}`);
  }

  /** 小程序分享埋点 —— 分享链路上报统一事件协议（对齐 wp_data_ops） */
  trackShare(channel: string, seed: string): void {
    // 埋点协议：event=share, engine=cocos-native, channel, seed
    console.info(`[CocosAdapter][event] share channel=${channel} seed=${seed}`);
  }

  /** 每帧更新（固定 30Hz） */
  async frame(deltaSeconds: number): Promise<any> {
    await this.middleware.update(deltaSeconds);
    this.tick += 1;
    const terrain = await this.middleware.generateTerrain(
      `${this.worldSeed}_${this.tick}`, 8, 8
    );
    return { terrain, tick: this.tick };
  }

  /** 切换到新世界（程序化生成，轻量复现） */
  async switchWorld(seed: string): Promise<void> {
    this.worldSeed = seed;
    this.tick = 0;
  }
}
