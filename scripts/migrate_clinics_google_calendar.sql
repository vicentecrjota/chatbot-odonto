-- Adiciona campo de Google Calendar à tabela clinics.
-- Executar uma única vez no Supabase SQL Editor.

ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS google_calendar_id text;

COMMENT ON COLUMN public.clinics.google_calendar_id IS
  'ID do Google Calendar da clínica (ex: abc123@group.calendar.google.com). Usado para agendamentos.';
