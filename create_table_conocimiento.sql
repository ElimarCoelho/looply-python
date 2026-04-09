-- Ejecutar en el SQL Editor de Supabase (https://supabase.com/dashboard)
-- Tabla para almacenar la base de conocimiento de clientes contactados

CREATE TABLE IF NOT EXISTS base_conocimiento (
    id BIGSERIAL PRIMARY KEY,
    phone_number TEXT NOT NULL UNIQUE,
    business_name TEXT DEFAULT '',
    knowledge_base TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsqueda rápida por teléfono
CREATE INDEX IF NOT EXISTS idx_base_conocimiento_phone ON base_conocimiento(phone_number);

-- Habilitar RLS (Row Level Security) - opcional
ALTER TABLE base_conocimiento ENABLE ROW LEVEL SECURITY;

-- Política para permitir todas las operaciones con la service key
CREATE POLICY "Allow all operations" ON base_conocimiento
    FOR ALL
    USING (true)
    WITH CHECK (true);
