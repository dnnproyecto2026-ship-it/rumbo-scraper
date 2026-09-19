-- Directorio académico: personas con múltiples roles y ámbitos.
-- Ejecutar una vez en Supabase SQL Editor.

create table if not exists personas (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nombre_completo text not null,
  email text,
  perfil_url text,
  formacion text,
  biografia text,
  fuente_url text,
  activa boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (universidad_id, nombre_completo)
);

create table if not exists roles_academicos (
  id uuid primary key default gen_random_uuid(),
  persona_id uuid not null references personas(id) on delete cascade,
  universidad_id uuid not null references universidades(id) on delete cascade,
  facultad_id uuid references facultades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete cascade,
  materia_id uuid references materias(id) on delete cascade,
  cargo text not null,
  tipo_rol text not null,
  es_autoridad boolean not null default false,
  vigente boolean not null default true,
  fuente_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists uq_roles_academicos_identidad
on roles_academicos (
  persona_id,
  coalesce(facultad_id, '00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(carrera_id, '00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(materia_id, '00000000-0000-0000-0000-000000000000'::uuid),
  cargo
);

create index if not exists idx_personas_universidad on personas(universidad_id);
create index if not exists idx_roles_persona on roles_academicos(persona_id);
create index if not exists idx_roles_facultad on roles_academicos(facultad_id);
create index if not exists idx_roles_carrera on roles_academicos(carrera_id);
create index if not exists idx_roles_materia on roles_academicos(materia_id);

drop trigger if exists trg_personas_updated on personas;
create trigger trg_personas_updated before update on personas
for each row execute function set_updated_at();

drop trigger if exists trg_roles_academicos_updated on roles_academicos;
create trigger trg_roles_academicos_updated before update on roles_academicos
for each row execute function set_updated_at();

alter table personas enable row level security;
alter table roles_academicos enable row level security;

grant select on personas, roles_academicos to anon, authenticated;
grant all on personas, roles_academicos to service_role;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='personas' and policyname='Lectura pública de personas') then
    create policy "Lectura pública de personas" on personas for select to anon, authenticated using (true);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='roles_academicos' and policyname='Lectura pública de roles académicos') then
    create policy "Lectura pública de roles académicos" on roles_academicos for select to anon, authenticated using (true);
  end if;
end $$;

create or replace view directorio_academico_view
with (security_invoker = true) as
select
  p.id as persona_id,
  p.nombre_completo,
  p.email,
  p.perfil_url,
  r.cargo,
  r.tipo_rol,
  r.es_autoridad,
  r.vigente,
  f.nombre_facultad,
  c.nombre_carrera,
  m.nombre_materia
from personas p
join roles_academicos r on r.persona_id = p.id
left join facultades f on f.id = r.facultad_id
left join carreras c on c.id = r.carrera_id
left join materias m on m.id = r.materia_id;

grant select on directorio_academico_view to anon, authenticated;
