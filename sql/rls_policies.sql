cat > /home/claude/hackforge/sql/storage_policies.sql << 'SQLEOF'
-- ============================================================
-- HackForge - Supabase Storage Bucket Policies
-- Run in Supabase SQL Editor
-- ============================================================

-- Create the storage bucket (run via Supabase Dashboard or API)
-- INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
-- VALUES ('hackforge-files', 'hackforge-files', FALSE, 104857600, NULL)
-- ON CONFLICT (id) DO NOTHING;

-- Storage access policies (based on team membership)
-- Users can only upload to their team's folder
CREATE POLICY "team_upload" ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'hackforge-files' AND
    (storage.foldername(name))[1] = 'teams' AND
    is_team_member(
      (storage.foldername(name))[2]::UUID,
      auth.uid()
    )
  );

-- Team members can download their team's files
CREATE POLICY "team_download" ON storage.objects FOR SELECT
  USING (
    bucket_id = 'hackforge-files' AND
    (storage.foldername(name))[1] = 'teams' AND
    is_team_member(
      (storage.foldername(name))[2]::UUID,
      auth.uid()
    )
  );

-- Team members can delete their team's files
CREATE POLICY "team_delete" ON storage.objects FOR DELETE
  USING (
    bucket_id = 'hackforge-files' AND
    (storage.foldername(name))[1] = 'teams' AND
    is_team_member(
      (storage.foldername(name))[2]::UUID,
      auth.uid()
    )
  );

-- Team members can update (move) their files
CREATE POLICY "team_update" ON storage.objects FOR UPDATE
  USING (
    bucket_id = 'hackforge-files' AND
    (storage.foldername(name))[1] = 'teams' AND
    is_team_member(
      (storage.foldername(name))[2]::UUID,
      auth.uid()
    )
  );
SQLEOF
echo "storage_policies.sql created" 