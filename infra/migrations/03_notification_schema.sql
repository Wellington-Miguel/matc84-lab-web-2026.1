-- infra/migrations/03_notification_schema.sql
-- Schema de notificações com rastreamento e preferências

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id VARCHAR(255) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    channels JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, sent, failed
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE
);

-- Índices para queries rápidas
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);

-- Tabela de preferências de notificação
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(20),
    push_token TEXT,
    preferences JSONB DEFAULT '{}', -- {notification_type: [channels]}
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_preferences_recipient ON notification_preferences(recipient_id);

-- Tabela de auditoria (opcional)
CREATE TABLE IF NOT EXISTS notification_audit (
    id BIGSERIAL PRIMARY KEY,
    notification_id UUID NOT NULL,
    event VARCHAR(50) NOT NULL,
    channel VARCHAR(20),
    status VARCHAR(20),
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (notification_id) REFERENCES notifications(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_notification ON notification_audit(notification_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON notification_audit(created_at DESC);
