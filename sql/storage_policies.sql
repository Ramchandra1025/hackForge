-- ============================================================
-- HACKFORGE - SUPABASE STORAGE POLICIES
-- ============================================================

-- Create storage buckets (run via Supabase dashboard or API)
-- INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
-- VALUES ('hackforge-files', 'hackforge-files', FALSE, 104857600, NULL);

-- ============================================================
-- BUCKET SETUP (via Supabase JS or Python client)
-- ============================================================

-- Bucket: hackforge-files (private, 100MB limit)
-- Folder structure:
--   teams/{team_id}/projects/{project_id}/files/{filename}
--   teams/{team_id}/avatars/{user_id}/{filename}
--   teams/{team_id}/whiteboards/{whiteboard_id}/{filename}

-- ============================================================
-- STORAGE RLS POLICIES
-- ============================================================

-- Drop existing policies
DROP POLICY IF EXISTS "team_members_can_upload" ON storage.objects;
DROP POLICY IF EXISTS "team_members_can_read" ON storage.objects;
DROP POLICY IF EXISTS "team_members_can_delete" ON storage.objects;
DROP POLICY IF EXISTS "team_members_can_update" ON storage.objects;

-- Allow team members to upload to their team folder
CREATE POLICY "team_members_can_upload"
ON storage.objects FOR INSERT
WITH CHECK (
    bucket_id = 'hackforge-files'
    AND (
        -- Extract team_id from path: teams/{team_id}/...
        EXISTS (
            SELECT 1 FROM memberships m
            JOIN teams t ON t.id = m.team_id
            WHERE m.user_id = auth.uid()
            AND m.is_active = TRUE
            AND (storage.foldername(name))[1] = 'teams'
            AND (storage.foldername(name))[2] = t.id::TEXT
        )
    )
);

-- Allow team members to read their team files
CREATE POLICY "team_members_can_read"
ON storage.objects FOR SELECT
USING (
    bucket_id = 'hackforge-files'
    AND (
        EXISTS (
            SELECT 1 FROM memberships m
            JOIN teams t ON t.id = m.team_id
            WHERE m.user_id = auth.uid()
            AND m.is_active = TRUE
            AND (storage.foldername(name))[1] = 'teams'
            AND (storage.foldername(name))[2] = t.id::TEXT
        )
    )
);

-- Allow team members to delete their team files
CREATE POLICY "team_members_can_delete"
ON storage.objects FOR DELETE
USING (
    bucket_id = 'hackforge-files'
    AND (
        EXISTS (
            SELECT 1 FROM memberships m
            JOIN teams t ON t.id = m.team_id
            WHERE m.user_id = auth.uid()
            AND m.is_active = TRUE
            AND m.role IN ('owner', 'admin', 'developer')
            AND (storage.foldername(name))[1] = 'teams'
            AND (storage.foldername(name))[2] = t.id::TEXT
        )
    )
);

-- Allow team members to update their team files
CREATE POLICY "team_members_can_update"
ON storage.objects FOR UPDATE
USING (
    bucket_id = 'hackforge-files'
    AND (
        EXISTS (
            SELECT 1 FROM memberships m
            JOIN teams t ON t.id = m.team_id
            WHERE m.user_id = auth.uid()
            AND m.is_active = TRUE
            AND (storage.foldername(name))[1] = 'teams'
            AND (storage.foldername(name))[2] = t.id::TEXT
        )
    )
);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Get team storage usage
CREATE OR REPLACE FUNCTION get_team_storage_usage(p_team_id UUID)
RETURNS TABLE(used_mb DECIMAL, quota_mb INTEGER, files_count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(f.size_bytes)::DECIMAL / 1048576, 0) as used_mb,
        t.storage_quota_mb,
        COUNT(f.id) as files_count
    FROM teams t
    LEFT JOIN files f ON f.team_id = t.id AND f.is_deleted = FALSE
    WHERE t.id = p_team_id
    GROUP BY t.storage_quota_mb;
END;
$$ LANGUAGE plpgsql;

-- Check team storage quota
CREATE OR REPLACE FUNCTION check_storage_quota(p_team_id UUID, p_new_file_bytes BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
    v_used_bytes BIGINT;
    v_quota_bytes BIGINT;
BEGIN
    SELECT 
        COALESCE(SUM(size_bytes), 0),
        t.storage_quota_mb * 1048576
    INTO v_used_bytes, v_quota_bytes
    FROM teams t
    LEFT JOIN files f ON f.team_id = t.id AND f.is_deleted = FALSE
    WHERE t.id = p_team_id
    GROUP BY t.storage_quota_mb;
    
    RETURN (v_used_bytes + p_new_file_bytes) <= v_quota_bytes;
END;
$$ LANGUAGE plpgsql;

-- Full-text search function
CREATE OR REPLACE FUNCTION search_workspace(p_team_id UUID, p_query TEXT)
RETURNS TABLE(
    entity_type VARCHAR,
    entity_id UUID,
    title TEXT,
    snippet TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        si.entity_type,
        si.entity_id,
        si.title,
        ts_headline('english', si.content, to_tsquery('english', p_query)) as snippet,
        ts_rank(si.search_vector, to_tsquery('english', p_query)) as rank
    FROM search_index si
    WHERE si.team_id = p_team_id
    AND si.search_vector @@ to_tsquery('english', p_query)
    ORDER BY rank DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

-- Cleanup expired OTPs
CREATE OR REPLACE FUNCTION cleanup_expired_otps()
RETURNS void AS $$
BEGIN
    DELETE FROM otp_codes WHERE expires_at < NOW();
    DELETE FROM pending_users WHERE expires_at < NOW();
    DELETE FROM login_sessions WHERE expires_at < NOW() AND is_active = FALSE;
END;
$$ LANGUAGE plpgsql;

-- Cleanup expired storage upload sessions
CREATE OR REPLACE FUNCTION cleanup_storage_sessions()
RETURNS void AS $$
BEGIN
    UPDATE storage_upload_sessions 
    SET status = 'expired'
    WHERE expires_at < NOW() AND status = 'pending';
END;
$$ LANGUAGE plpgsql;
