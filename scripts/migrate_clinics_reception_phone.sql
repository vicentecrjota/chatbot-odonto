-- Adiciona número da recepção à tabela clinics.
-- Executar uma única vez no Supabase SQL Editor.

ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS reception_phone text;

COMMENT ON COLUMN public.clinics.reception_phone IS
  'Número WhatsApp da recepção da clínica (formato internacional, ex: 5548999999999). Recebe alertas de handoff.';
