/**
 * Upload Queue Management
 */

window.HF = window.HF || {};

const HFUploadQueue = {
  queue: [],
  processing: false,

  /**
   * Add to queue
   */
  addToQueue(file, options = {}) {
    const queueItem = {
      id: HFHelpers.generateUUID(),
      file,
      options,
      status: 'queued',
      progress: 0
    };

    this.queue.push(queueItem);
    return queueItem.id;
  },

  /**
   * Start processing queue
   */
  async processQueue() {
    if (this.processing) return;
    this.processing = true;

    while (this.queue.length > 0) {
      const item = this.queue[0];

      try {
        await HFUploadManager.uploadFile(
          item.file,
          {
            ...item.options,
            onProgress: (progress) => {
              item.progress = progress;
              if (item.options.onProgress) item.options.onProgress(progress);
            },
            onComplete: (result) => {
              item.status = 'completed';
              if (item.options.onComplete) item.options.onComplete(result);
              this.queue.shift();
            },
            onError: (error) => {
              item.status = 'error';
              if (item.options.onError) item.options.onError(error);
            }
          }
        );
      } catch (error) {
        item.status = 'error';
        console.error('Queue processing error:', error);
      }
    }

    this.processing = false;
  },

  /**
   * Get queue status
   */
  getQueueStatus() {
    return {
      total: this.queue.length,
      completed: this.queue.filter(i => i.status === 'completed').length,
      items: this.queue
    };
  },

  /**
   * Clear queue
   */
  clearQueue() {
    this.queue = [];
  }
};

window.HFUploadQueue = HFUploadQueue;
