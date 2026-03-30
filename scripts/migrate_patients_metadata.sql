-- Adiciona coluna metadata à tabela patients para contexto clínico do paciente.
-- Executar uma única vez no Supabase SQL Editor.

ALTER TABLE public.patients
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.patients.metadata IS
  'Contexto clínico extraído automaticamente pelo bot (procedimento de interesse, sintomas, urgência, observações).';
