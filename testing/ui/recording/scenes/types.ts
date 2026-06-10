import type { Page } from 'playwright';
import type { RecordingProfile } from '../config';
import type { SceneResult } from '../helpers';

export interface SceneDefinition {
  id: string;
  title: string;
  description?: string;
  profiles: RecordingProfile[] | 'both';
  optional?: boolean;
  timingKey: string;
  record: (page: Page) => Promise<SceneResult>;
}

export function profilesFor(scene: SceneDefinition): RecordingProfile[] {
  if (scene.profiles === 'both') return ['gcp', 'local'];
  return scene.profiles;
}
