-- Adiciona campos de identificação de canal à tabela clinics.
-- Executar uma única vez no Supabase SQL Editor.

ALTER TABLE public.clinics
  ADD COLUMN IF NOT EXISTS whatsapp_phone_number_id text,
  ADD COLUMN IF NOT EXISTS instagram_page_id text;

-- Índices para lookup rápido nos webhooks
CREATE UNIQUE INDEX IF NOT EXISTS clinics_whatsapp_phone_number_id_idx
  ON public.clinics (whatsapp_phone_number_id)
  WHERE whatsapp_phone_number_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS clinics_instagram_page_id_idx
  ON public.clinics (instagram_page_id)
  WHERE instagram_page_id IS NOT NULL;

COMMENT ON COLUMN public.clinics.whatsapp_phone_number_id IS
  'ID do número WhatsApp Business (phone_number_id da Meta API). Usado para rotear webhooks.';

COMMENT ON COLUMN public.clinics.instagram_page_id IS
  'ID da página do Instagram Business. Usado para rotear webhooks.';
