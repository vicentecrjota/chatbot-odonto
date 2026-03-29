-- Schema PostgreSQL para chatbot-odonto
-- Requer extensão pgvector para colunas embedding.
--
-- RLS: a aplicação deve definir o contexto do tenant antes das queries, p.ex.:
--   SET LOCAL app.current_clinic_id = 'uuid-da-clinica';
-- (ou SET na sessão). Políticas comparam clinic_id com tenant_clinic_id().
--
-- message_queue inclui clinic_id para permitir isolamento por clínica nas políticas RLS.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------------
-- Função de sessão para multi-tenant (RLS)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.tenant_clinic_id()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT NULLIF(btrim(current_setting('app.current_clinic_id', true)), '')::uuid;
$$;

COMMENT ON FUNCTION public.tenant_clinic_id() IS
  'UUID da clínica do tenant atual; definir com SET [LOCAL] app.current_clinic_id.';

-- -----------------------------------------------------------------------------
-- Tabelas
-- -----------------------------------------------------------------------------

CREATE TABLE public.clinics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  whatsapp_number text NOT NULL,
  plan_type text NOT NULL,
  rag_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  patient_phone text NOT NULL,
  messages jsonb NOT NULL DEFAULT '[]'::jsonb,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz
);

CREATE INDEX conversations_clinic_id_idx ON public.conversations (clinic_id);
CREATE INDEX conversations_patient_phone_idx ON public.conversations (patient_phone);

CREATE TABLE public.patients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  name text NOT NULL,
  phone text NOT NULL,
  consent_given boolean NOT NULL DEFAULT false,
  consent_at timestamptz,
  CONSTRAINT patients_clinic_phone_uniq UNIQUE (clinic_id, phone),
  CONSTRAINT patients_clinic_id_id_key UNIQUE (clinic_id, id)
);

CREATE INDEX patients_clinic_id_idx ON public.patients (clinic_id);

CREATE TABLE public.appointments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  patient_id uuid NOT NULL,
  datetime timestamptz NOT NULL,
  procedure text NOT NULL,
  status text NOT NULL,
  CONSTRAINT appointments_clinic_patient_fk
    FOREIGN KEY (clinic_id, patient_id)
    REFERENCES public.patients (clinic_id, id)
    ON DELETE CASCADE
);

CREATE INDEX appointments_clinic_id_idx ON public.appointments (clinic_id);
CREATE INDEX appointments_patient_id_idx ON public.appointments (patient_id);
CREATE INDEX appointments_datetime_idx ON public.appointments (datetime);

CREATE TABLE public.rag_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  content text NOT NULL,
  embedding vector(1536) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX rag_documents_clinic_id_idx ON public.rag_documents (clinic_id);
CREATE INDEX rag_documents_embedding_ivfflat_idx ON public.rag_documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  action text NOT NULL,
  entity text NOT NULL,
  timestamp timestamptz NOT NULL DEFAULT now(),
  ip inet
);

CREATE INDEX audit_logs_clinic_id_idx ON public.audit_logs (clinic_id);
CREATE INDEX audit_logs_timestamp_idx ON public.audit_logs (timestamp);

CREATE TABLE public.message_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  payload jsonb NOT NULL,
  status text NOT NULL,
  scheduled_at timestamptz NOT NULL,
  processed_at timestamptz
);

CREATE INDEX message_queue_clinic_id_idx ON public.message_queue (clinic_id);
CREATE INDEX message_queue_status_scheduled_idx
  ON public.message_queue (status, scheduled_at);

-- -----------------------------------------------------------------------------
-- Row Level Security
-- -----------------------------------------------------------------------------

ALTER TABLE public.clinics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_queue ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.clinics FORCE ROW LEVEL SECURITY;
ALTER TABLE public.conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.patients FORCE ROW LEVEL SECURITY;
ALTER TABLE public.appointments FORCE ROW LEVEL SECURITY;
ALTER TABLE public.rag_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.message_queue FORCE ROW LEVEL SECURITY;

-- clinics: uma linha por tenant; visível só quando id = contexto
CREATE POLICY clinics_tenant_isolation
  ON public.clinics
  FOR ALL
  USING (id = tenant_clinic_id())
  WITH CHECK (id = tenant_clinic_id());

CREATE POLICY conversations_tenant_isolation
  ON public.conversations
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

CREATE POLICY patients_tenant_isolation
  ON public.patients
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

CREATE POLICY appointments_tenant_isolation
  ON public.appointments
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

CREATE POLICY rag_documents_tenant_isolation
  ON public.rag_documents
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

CREATE POLICY audit_logs_tenant_isolation
  ON public.audit_logs
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

CREATE POLICY message_queue_tenant_isolation
  ON public.message_queue
  FOR ALL
  USING (clinic_id = tenant_clinic_id())
  WITH CHECK (clinic_id = tenant_clinic_id());

COMMIT;
