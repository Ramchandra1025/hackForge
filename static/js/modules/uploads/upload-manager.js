/**
 * Upload Manager
 */

window.HF = window.HF || {};

const HFUploadManager = {
  uploads: {},
  maxConcurrent: 3,
  activeUploads: 0,

  /**
   * Upload file
   */
  async uploadFile(file, options = {}) {
    const {
      projectId = null,
      teamId = null,
      onProgress = null,
      onComplete = null,
      onError = null,
      chunkSize = 5 * 1024 * 1024 // 5MB chunks
    } = options;

    // Validate file
    const validation = HFValidators.validateFileUpload(file);
    if (!validation.valid) {
      if (onError) onError(validation.error);
      HFToast.show(validation.error, 'error');
      return null;
    }

    const uploadId = HFHelpers.generateUUID();
    const upload = {
      id: uploadId,
      file,
      progress: 0,
      status: 'queued',
      chunks: Math.ceil(file.size / chunkSize)
    };

    this.uploads[uploadId] = upload;

    // Wait for concurrent limit
    await this._waitForSlot();

    return this._performUpload(uploadId, projectId, teamId, chunkSize, onProgress, onComplete, onError);
  },

  /**
   * Perform upload
   */
  async _performUpload(uploadId, projectId, teamId, chunkSize, onProgress, onComplete, onError) {
    const upload = this.uploads[uploadId];
    upload.status = 'uploading';
    this.activeUploads++;
    let lastResponse = null;

    try {
      const file = upload.file;
      const chunks = Math.ceil(file.size / chunkSize);

      for (let i = 0; i < chunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const chunk = file.slice(start, end);

        const formData = new FormData();
        formData.append('file', chunk);
        formData.append('chunkIndex', i);
        formData.append('totalChunks', chunks);
        formData.append('uploadId', uploadId);
        formData.append('fileName', file.name);
        if (projectId) formData.append('projectId', projectId);
        if (teamId) formData.append('teamId', teamId);

        lastResponse = await fetch('/api/files/upload/chunk', {
          method: 'POST',
          body: formData
        });

        if (!lastResponse.ok) {
          throw new Error(`Upload failed: ${lastResponse.statusText}`);
        }

        const progress = ((i + 1) / chunks) * 100;
        upload.progress = progress;
        if (onProgress) onProgress(progress);
      }

      upload.status = 'completed';
      if (onComplete) {
        const result = lastResponse ? await lastResponse.json() : { success: true };
        onComplete(result);
      }

    } catch (error) {
      upload.status = 'failed';
      if (onError) onError(error.message);
      HFToast.show(error.message, 'error');
    } finally {
      this.activeUploads--;
    }

    return upload;
  },

  /**
   * Wait for upload slot
   */
  async _waitForSlot() {
    while (this.activeUploads >= this.maxConcurrent) {
      await HFHelpers.sleep(100);
    }
  },

  /**
   * Get upload status
   */
  getUploadStatus(uploadId) {
    return this.uploads[uploadId] || null;
  },

  /**
   * Cancel upload
   */
  cancelUpload(uploadId) {
    const upload = this.uploads[uploadId];
    if (upload) {
      upload.status = 'cancelled';
    }
  }
};

window.HFUploadManager = HFUploadManager;
