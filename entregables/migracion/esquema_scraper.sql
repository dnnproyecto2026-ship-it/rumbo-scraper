-- Esquema PROVISORIO de la base del scraper, reconstruido del código (contracts.py y los loaders).
-- Pegarlo entero en el SQL Editor de la base nueva. Es idempotente: se puede correr más de una vez.
-- Cuando el proyecto viejo vuelva a responder, `migrar_base esquema` genera el exacto y se compara.
-- Los tipos dudosos son text: una columna de texto acepta cualquier valor y no rompe una carga.

create extension if not exists pgcrypto;

create table if not exists localidades (
  id uuid primary key default gen_random_uuid(),
  nombre_localidad text not null,
  provincia text not null,
  codigo_postal text,
  unique (nombre_localidad, provincia)
);

create table if not exists universidades (
  id uuid primary key default gen_random_uuid(),
  nombre_oficial text not null unique,
  nombre_corto text,
  tipo_gestion text,
  tipo_institucion text,
  anio_fundacion integer,
  sitio_web text,
  telefono_area text,
  telefono_numero text,
  mail_contacto text,
  instagram text, tiktok text, linkedin text, twitter text, facebook text, youtube text,
  created_at timestamptz default now()
);

create table if not exists sedes (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nombre_sede text not null,
  localidad_id uuid references localidades(id),
  calle text, numero text, tipo_sede text,
  unique (universidad_id, nombre_sede)
);

create table if not exists facultades (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nombre_facultad text not null,
  tipo_unidad text,
  unique (universidad_id, nombre_facultad, tipo_unidad)
);

create table if not exists facultades_sedes (
  id uuid primary key default gen_random_uuid(),
  facultad_id uuid not null references facultades(id) on delete cascade,
  sede_id uuid not null references sedes(id) on delete cascade,
  es_sede_principal boolean default false,
  unique (facultad_id, sede_id)
);

create table if not exists carreras (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  facultad_id uuid references facultades(id) on delete set null,
  nombre_carrera text not null,
  denominacion_canonica text,
  nivel text,
  titulo_otorgado text,
  tiene_titulo_intermedio boolean,
  duracion_anios numeric,
  descripcion_breve text,
  cantidad_materias_total integer,
  unique (universidad_id, nombre_carrera)
);

create table if not exists ofertas_academicas (
  id uuid primary key default gen_random_uuid(),
  carrera_id uuid not null references carreras(id) on delete cascade,
  sede_id uuid not null references sedes(id) on delete cascade,
  modalidad text,
  regimen_ingreso text,
  coneau_resolucion text,
  coneau_vigencia_hasta text,
  tiene_pasantias boolean,
  tiene_bolsa_trabajo boolean,
  url_oficial text,
  activa boolean default true
);

create table if not exists ciclos_ingreso (
  id uuid primary key default gen_random_uuid(),
  oferta_id uuid not null references ofertas_academicas(id) on delete cascade,
  ciclo_anio integer,
  ciclo_nombre text,
  cupo_ingresantes integer,
  fecha_apertura_inscripcion text,
  fecha_cierre_inscripcion text,
  estado text,
  unique (oferta_id, ciclo_anio, ciclo_nombre)
);

create table if not exists turnos_anio (
  id uuid primary key default gen_random_uuid(),
  oferta_id uuid not null references ofertas_academicas(id) on delete cascade,
  anio_carrera integer,
  turno text
);

create table if not exists aranceles (
  id uuid primary key default gen_random_uuid(),
  oferta_id uuid not null references ofertas_academicas(id) on delete cascade,
  vigencia_desde text,
  monto_mensual numeric, monto_matricula numeric,
  moneda text, motivo_cambio text
);

create table if not exists areas_tematicas (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique
);

create table if not exists posgrados (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  facultad_id uuid references facultades(id) on delete set null,
  sede_id uuid references sedes(id) on delete set null,
  nombre_programa text not null,
  tipo_posgrado text,
  titulo_otorgado text,
  modalidad text,
  duracion_meses integer,
  requiere_tesis_trabajo_final boolean,
  requisito_titulo_previo text,
  cohorte_inicio text,
  costo_total_programa numeric,
  moneda text,
  descripcion_breve text,
  url_oficial text,
  unique (universidad_id, nombre_programa)
);

create table if not exists materias (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete cascade,
  posgrado_id uuid references posgrados(id) on delete cascade,
  nombre_materia text not null,
  anio_cursada integer,
  turno text,
  area_tematica_id uuid references areas_tematicas(id) on delete set null,
  descripcion_breve text,
  regimen text,
  carga_horaria_semanal numeric
);
create index if not exists materias_universidad_idx on materias (universidad_id);
create index if not exists materias_carrera_idx on materias (carrera_id);

create table if not exists actividades (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete cascade,
  posgrado_id uuid references posgrados(id) on delete cascade,
  tipo_actividad text,
  nombre_actividad text,
  obligatoria boolean,
  carga_horaria_total numeric,
  descripcion_breve text
);

create table if not exists autoridades (
  id uuid primary key default gen_random_uuid(),
  facultad_id uuid references facultades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete cascade,
  cargo text, tipo text, nombre_autoridad text
);

create table if not exists contactos (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid references universidades(id) on delete cascade,
  facultad_id uuid references facultades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete cascade,
  canal text,
  usuario_o_direccion text
);

create table if not exists becas (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nombre_beca text, nivel text, tipo_beca text,
  cobertura_descripcion text,
  porcentaje_maximo numeric,
  requisitos text, proceso_postulacion text, renovacion text,
  fecha_cierre text, url_postulacion text, contacto text, fuente_url text
);

create table if not exists servicios_estudiantiles (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  sede_id uuid references sedes(id) on delete set null,
  categoria text, nombre_servicio text, descripcion text, contacto text, url text, fuente_url text
);

create table if not exists actividades_extracurriculares (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  sede_id uuid references sedes(id) on delete set null,
  categoria text, nombre_actividad text, descripcion text, contacto text, url text, fuente_url text
);

create table if not exists alojamientos (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  sede_id uuid references sedes(id) on delete set null,
  tipo_apoyo text, tipo_alojamiento text,
  residencia_propia boolean,
  descripcion text, contacto text, url text, fuente_url text
);

create table if not exists programas_internacionales (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nivel text, tipo_programa text, nombre_programa text,
  cantidad_convenios integer,
  duracion_maxima text,
  reconocimiento_academico boolean,
  arancel_destino_cubierto text,
  requisitos text, url text, fuente_url text
);

create table if not exists convenios_intercambio (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  carrera_id uuid references carreras(id) on delete set null,
  programa_origen text,
  universidad_destino text,
  ciudad text, pais text,
  latitud numeric, longitud numeric,
  observaciones text, fuente_url text
);

create table if not exists personas (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  nombre_completo text not null,
  email text, formacion text, biografia text,
  perfil_url text, fuente_url text,
  activa boolean default true,
  unique (universidad_id, nombre_completo)
);

create table if not exists roles_academicos (
  id uuid primary key default gen_random_uuid(),
  persona_id uuid not null references personas(id) on delete cascade,
  universidad_id uuid not null references universidades(id) on delete cascade,
  facultad_id uuid references facultades(id) on delete set null,
  carrera_id uuid references carreras(id) on delete set null,
  materia_id uuid references materias(id) on delete set null,
  cargo text, tipo_rol text,
  es_autoridad boolean default false,
  vigente boolean default true,
  fuente_url text
);

create table if not exists materias_catalogo (
  id uuid primary key default gen_random_uuid(),
  universidad_id uuid not null references universidades(id) on delete cascade,
  codigo text not null,
  nombre text,
  fuente_url text,
  activa boolean default true,
  unique (universidad_id, codigo)
);

create table if not exists materias_catalogo_vinculos (
  id uuid primary key default gen_random_uuid(),
  materia_id uuid not null references materias(id) on delete cascade,
  materia_catalogo_id uuid not null references materias_catalogo(id) on delete cascade,
  metodo text,
  confianza numeric,
  unique (materia_id, materia_catalogo_id)
);

create table if not exists comisiones_materia (
  id uuid primary key default gen_random_uuid(),
  materia_catalogo_id uuid not null references materias_catalogo(id) on delete cascade,
  anio integer, semestre text, seccion text,
  contenido text, condiciones_aprobacion text, programa_url text, fuente_url text,
  unique (materia_catalogo_id, anio, semestre, seccion)
);

create table if not exists horarios_comision (
  id uuid primary key default gen_random_uuid(),
  comision_id uuid not null references comisiones_materia(id) on delete cascade,
  tipo_clase text, dia text, hora_inicio text, hora_fin text
);

create table if not exists docentes_comision (
  id uuid primary key default gen_random_uuid(),
  comision_id uuid not null references comisiones_materia(id) on delete cascade,
  persona_id uuid references personas(id) on delete set null,
  nombre_docente_fuente text,
  tipo_clase text
);

create table if not exists pendientes_datos (
  id uuid primary key default gen_random_uuid(),
  clave text not null unique,
  universidad_id uuid references universidades(id) on delete cascade,
  entidad_tipo text, entidad_id text, campo text, prioridad text,
  motivo text, accion_recomendada text,
  estado text default 'pendiente',
  ultima_deteccion_at timestamptz,
  resuelto_at timestamptz
);

-- El scraper entra con la clave de servicio: las tablas quedan cerradas a la clave pública.
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
end $$;

-- Vaciar el esquema public borra los permisos de Supabase: la clave de servicio los necesita para escribir.
grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;

notify pgrst, 'reload schema';
