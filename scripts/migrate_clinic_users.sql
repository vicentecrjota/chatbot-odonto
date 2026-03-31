-- Tabela que vincula usuários do Supabase Auth às clínicas.
-- Um usuário pode gerenciar apenas uma clínica (simplificação inicial).

CREATE TABLE IF NOT EXISTS public.clinic_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  clinic_id uuid NOT NULL REFERENCES public.clinics (id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'admin',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT clinic_users_user_clinic_uniq UNIQUE (user_id, clinic_id)
);

CREATE INDEX IF NOT EXISTS clinic_users_user_id_idx ON public.clinic_users (user_id);
CREATE INDEX IF NOT EXISTS clinic_users_clinic_id_idx ON public.clinic_users (clinic_id);

-- RLS: cada usuário só enxerga seu próprio vínculo
ALTER TABLE public.clinic_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY clinic_users_self
  ON public.clinic_users
  FOR SELECT
  USING (user_id = auth.uid());
