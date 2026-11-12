from pathlib import Path

sql = """-- Nest Realtor V2: agent identity and preferences
-- Run this in the Supabase SQL Editor.
-- Safe to re-run: tables are created only if missing and policies are replaced.

create extension if not exists pgcrypto;

create table if not exists public.agents (
    user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.agents enable row level security;

drop policy if exists "Agents can view their own record" on public.agents;
create policy "Agents can view their own record"
on public.agents for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Agents can create their own record" on public.agents;
create policy "Agents can create their own record"
on public.agents for insert to authenticated
with check (auth.uid() = user_id);


create table if not exists public.agent_preferences_v2 (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique
        references public.agents(user_id) on delete cascade,
    province text,
    city text,
    area text,
    property_type text,
    min_price numeric,
    max_price numeric,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.agent_preferences_v2 enable row level security;

drop policy if exists "Agents can view their own preferences" on public.agent_preferences_v2;
create policy "Agents can view their own preferences"
on public.agent_preferences_v2 for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Agents can create their own preferences" on public.agent_preferences_v2;
create policy "Agents can create their own preferences"
on public.agent_preferences_v2 for insert to authenticated
with check (auth.uid() = user_id);

drop policy if exists "Agents can update their own preferences" on public.agent_preferences_v2;
create policy "Agents can update their own preferences"
on public.agent_preferences_v2 for update to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);


create or replace function public.set_agent_preferences_v2_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_agent_preferences_v2_updated_at
on public.agent_preferences_v2;

create trigger set_agent_preferences_v2_updated_at
before update on public.agent_preferences_v2
for each row
execute function public.set_agent_preferences_v2_updated_at();
"""

path = Path("/mnt/data/nest_realtor_v2_agent_preferences.sql")
path.write_text(sql, encoding="utf-8")
print(f"Created and verified: {path} ({path.stat().st_size} bytes)")
