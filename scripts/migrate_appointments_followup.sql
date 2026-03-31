-- Adiciona coluna followup_sent à tabela appointments
-- para controle de envio de mensagem pós-consulta.

ALTER TABLE public.appointments
  ADD COLUMN IF NOT EXISTS followup_sent boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS appointments_followup_pending_idx
  ON public.appointments (datetime)
  WHERE followup_sent = false;
