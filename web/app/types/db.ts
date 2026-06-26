export type Role = 'admin' | 'supervisor' | 'atendente'
export type JobStatus = 'na_fila' | 'executando' | 'concluido' | 'erro'

export interface Perfil {
  id: string
  full_name: string | null
  role: Role
  active: boolean
}

export interface Sistema {
  id: string
  slug: string
  name: string
  description: string | null
  allowed_roles: Role[]
  kind: 'job' | 'inbox'
  param_schema: Record<string, any>
  sort_order: number
  active: boolean
}

export interface Job {
  id: string
  system_slug: string
  requested_by: string
  status: JobStatus
  params: Record<string, any>
  error: string | null
  result_path: string | null
  result_preview: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface JobLog {
  id: number
  job_id: string
  level: 'info' | 'warn' | 'error' | 'debug'
  line: string
  created_at: string
}

export type GiganetStatus = 'pending' | 'approved' | 'rejected'

export interface GiganetReview {
  id: string
  review_id: string | null
  reviewer_name: string | null
  star_rating: number | null
  comment: string | null
  ai_response: string
  final_response: string | null
  status: GiganetStatus
  resume_url: string | null
  decided_at: string | null
  created_at: string
}

export interface AuditEntry {
  id: number
  user_id: string | null
  action: string
  detail: Record<string, any>
  created_at: string
}
