import { apiFetch } from '@/api/client'
import type { KnowledgePoint } from '@/types/api'

/** 知识点目录（id / level1 / level2 中文名），用于前端把 id 显示成中文。 */
export const listKnowledgePoints = () =>
  apiFetch<KnowledgePoint[]>('/knowledge-points')
