import type { AddOptions, AddResult, SearchOptions, EntitiesOptions, RelatedOptions, CompressOptions, CompressResult, MemDogConfig } from "./types.js";
import { MemDogClient } from "./client.js";

/**
 * High-level 7-method facade for the memdog API.
 *
 * For full API coverage (~80 methods) use {@link MemDogClient} directly,
 * accessible via the {@link MemDog.client} property.
 *
 * @example
 * ```ts
 * const m = new MemDog({ baseUrl: "http://localhost:8080", apiKey: "key" });
 * const { dataId } = await m.add("Hello world", { tags: ["greeting"] });
 * const results = await m.search("hello", { limit: 5 });
 * await m.delete(dataId);
 *
 * // Access the full client for advanced operations
 * await m.client.semanticSearch("hello", { searchMode: "hybrid" });
 * ```
 */
export class MemDog {
  private readonly _client: MemDogClient;
  private readonly userId?: string;

  constructor(config: MemDogConfig) {
    this._client = new MemDogClient(config);
    this.userId = config.userId;
  }

  /** Access the full MemDogClient for advanced operations. */
  get client(): MemDogClient {
    return this._client;
  }

  // ---------------------------------------------------------------------------
  // add
  // ---------------------------------------------------------------------------

  async add(content?: string, opts: AddOptions = {}): Promise<AddResult> {
    const uid = opts.userId ?? this.userId;
    const createOpts: Parameters<MemDogClient["createData"]>[0] = {};
    if (content !== undefined) createOpts.content = content;
    if (opts.file) createOpts.file = opts.file;
    if (opts.name) createOpts.name = opts.name;
    if (opts.description) createOpts.description = opts.description;
    if (opts.tags?.length) createOpts.tags = opts.tags;

    const memIds: string[] = [];
    if (opts.memoryId) memIds.push(opts.memoryId);
    if (opts.memoryIds?.length) memIds.push(...opts.memoryIds);
    if (memIds.length) createOpts.memoryIds = memIds;

    const data = await this._client.createData(createOpts);
    const dataId = (data.data_id ?? data.id) as string;
    const result: AddResult = { dataId, memoryId: opts.memoryId };

    if (opts.memoryType && !opts.memoryId) {
      const today = new Date().toISOString().slice(0, 10);
      const memName = `auto-${opts.memoryType}-${today}`;
      let mid = await this.findAutoMemory(opts.memoryType, memName, uid);

      if (!mid) {
        const memPayload: Record<string, unknown> = { memory_type: opts.memoryType, name: memName };
        if (uid) memPayload.user_id = uid;
        const memData = await this._client.createMemory({
          memoryType: opts.memoryType,
          name: memName,
          userId: uid,
        });
        mid = (memData.memory_id ?? memData.id) as string;
      }

      if (mid && dataId) {
        await this._client.addDataToMemory(mid, [dataId]);
      }
      result.memoryId = mid;
    }

    return result;
  }

  private async findAutoMemory(memoryType: string, name: string, userId?: string): Promise<string | undefined> {
    try {
      const data = await this._client.listMemories({ memoryType, limit: 50, userId });
      const items: Record<string, unknown>[] = Array.isArray(data)
        ? data
        : ((data as Record<string, unknown>).items as Record<string, unknown>[]) ?? [];
      for (const mem of items) {
        if (mem.name === name) return (mem.memory_id ?? mem.id) as string;
      }
    } catch { /* swallow */ }
    return undefined;
  }

  // ---------------------------------------------------------------------------
  // search
  // ---------------------------------------------------------------------------

  async search(query: string, opts: SearchOptions = {}): Promise<Record<string, unknown>[]> {
    const uid = opts.userId ?? this.userId;
    const limit = opts.limit ?? 10;

    if (opts.useAi) {
      const data = await this._client.aiQuery(query, { memoryIds: opts.memoryIds });
      return Array.isArray(data) ? data : [data as Record<string, unknown>];
    }

    if (opts.memoryType) {
      const data = await this._client.listMemories({ memoryType: opts.memoryType, limit, userId: uid });
      const items: Record<string, unknown>[] = Array.isArray(data)
        ? data
        : ((data as Record<string, unknown>).items as Record<string, unknown>[]) ?? [];
      return items.slice(0, limit);
    }

    const data = await this._client.listUserData({ user: uid, format: "meta", limit });
    const items: Record<string, unknown>[] = Array.isArray(data)
      ? data
      : ((data as Record<string, unknown>).items as Record<string, unknown>[]) ?? [];
    return items;
  }

  // ---------------------------------------------------------------------------
  // get
  // ---------------------------------------------------------------------------

  async get(dataId: string, version?: number): Promise<Record<string, unknown>> {
    const content = await this._client.getData(dataId, { version });
    let meta: Record<string, unknown> = {};
    try { meta = (await this._client.getMetadata(dataId)) as Record<string, unknown>; } catch { /* optional */ }
    return { dataId, ...meta, content };
  }

  // ---------------------------------------------------------------------------
  // delete
  // ---------------------------------------------------------------------------

  async delete(dataId: string): Promise<boolean> {
    await this._client.deleteData(dataId);
    return true;
  }

  // ---------------------------------------------------------------------------
  // entities
  // ---------------------------------------------------------------------------

  async entities(query: string, opts: EntitiesOptions = {}): Promise<Record<string, unknown>[]> {
    return this._client.searchEntities(query, {
      userId: opts.userId ?? this.userId,
      entityType: opts.entityType,
      limit: opts.limit,
    });
  }

  // ---------------------------------------------------------------------------
  // related
  // ---------------------------------------------------------------------------

  async related(dataId: string, opts: RelatedOptions = {}): Promise<Record<string, unknown>[]> {
    return this._client.getDataEntities(dataId, { userId: opts.userId ?? this.userId });
  }

  // ---------------------------------------------------------------------------
  // compress
  // ---------------------------------------------------------------------------

  async compress(memoryId: string, opts: CompressOptions = {}): Promise<CompressResult> {
    return (await this._client.compressMemory(memoryId, {
      archiveOriginals: opts.archiveOriginals,
      maxSummaryLength: opts.maxSummaryLength,
      userId: opts.userId ?? this.userId,
    })) as CompressResult;
  }
}
