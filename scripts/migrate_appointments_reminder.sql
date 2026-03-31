-- Adiciona coluna reminder_sent à tabela appointments
-- para controle de envio de lembrete 24h antes da consulta.

ALTER TABLE public.appointments
  ADD COLUMN IF NOT EXISTS reminder_sent boolean NOT NULL DEFAULT false;

-- Índice parcial: apenas consultas pendentes de lembrete — queries do scheduler ficam rápidas.
CREATE INDEX IF NOT EXISTS appointments_reminder_pending_idx
  ON public.appointments (datetime)
  WHERE reminder_sent = false;
