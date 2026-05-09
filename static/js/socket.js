/**
 * Socket.IO Client Manager
 */

window.HF = window.HF || {};

const HFSocket = {
  socket: null,
  listeners: {},
  reconnectAttempts: 0,
  maxReconnectAttempts: 10,
  isConnected: false,

  /**
   * Initialize Socket.IO
   */
  init() {
    if (!window.io) {
      console.error('Socket.IO library not loaded');
      return;
    }

    // Import Socket.IO client
    this.socket = io({
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts
    });

    // Connection events
    this.socket.on('connect', () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      console.log('Connected to server');
      this._emit('connection', {});
    });

    this.socket.on('disconnect', () => {
      this.isConnected = false;
      console.log('Disconnected from server');
      this._emit('disconnection', {});
    });

    this.socket.on('connect_error', (error) => {
      console.error('Connection error:', error);
      this.reconnectAttempts++;
    });

    // Setup event listeners
    this._setupListeners();
  },

  /**
   * Setup event listeners
   */
  _setupListeners() {
    // Presence events
    this.socket.on('presence:online', (data) => this._emit('presence:online', data));
    this.socket.on('presence:offline', (data) => this._emit('presence:offline', data));

    // Editor events
    this.socket.on('editor:change', (data) => this._emit('editor:change', data));
    this.socket.on('cursor:move', (data) => this._emit('cursor:move', data));

    // Chat events
    this.socket.on('chat:message', (data) => this._emit('chat:message', data));
    this.socket.on('chat:typing', (data) => this._emit('chat:typing', data));

    // Whiteboard events
    this.socket.on('whiteboard:state', (data) => {
      this._emit('whiteboard:state', data);
      this._emit('whiteboard:sync', data);
    });
    this.socket.on('whiteboard:sync', (data) => this._emit('whiteboard:sync', data));
    this.socket.on('whiteboard:draw', (data) => this._emit('whiteboard:draw', data));
    this.socket.on('whiteboard:draw_update', (data) => this._emit('whiteboard:draw', data));
    this.socket.on('whiteboard:erase_update', (data) => this._emit('whiteboard:erase', data));
    this.socket.on('whiteboard:cleared', (data) => this._emit('whiteboard:clear', data));
    this.socket.on('whiteboard:saved', (data) => this._emit('whiteboard:save', data));
    this.socket.on('whiteboard:cursor_update', (data) => this._emit('whiteboard:cursor', data));
    this.socket.on('whiteboard:element_updated', (data) => this._emit('whiteboard:element_update', data));

    // Task events
    this.socket.on('task:update', (data) => this._emit('task:update', data));

    // Notification events
    this.socket.on('notification:new', (data) => this._emit('notification:new', data));

    // File events
    this.socket.on('file:update', (data) => this._emit('file:update', data));
  },

  /**
   * On event
   */
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  },

  /**
   * Off event
   */
  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  },

  /**
   * Emit event to listeners
   */
  _emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in listener for ${event}:`, error);
        }
      });
    }
  },

  /**
   * Emit event to server
   */
  emit(event, data) {
    if (this.isConnected) {
      this.socket.emit(event, data);
    } else {
      console.warn('Socket not connected');
    }
  },

  /**
   * Send editor change
   */
  sendEditorChange(projectId, changes) {
    this.emit('editor:change', {
      projectId,
      changes,
      timestamp: new Date().toISOString()
    });
  },

  /**
   * Send cursor move
   */
  sendCursorMove(projectId, line, column) {
    this.emit('cursor:move', {
      projectId,
      line,
      column,
      userId: HFState.currentUser?.id,
      timestamp: new Date().toISOString()
    });
  },

  /**
   * Send chat message
   */
  sendChatMessage(roomId, message) {
    this.emit('chat:message', {
      roomId,
      message,
      userId: HFState.currentUser?.id,
      timestamp: new Date().toISOString()
    });
  },

  /**
   * Send whiteboard draw
   */
  sendWhiteboardDraw(boardId, data) {
    this.emit('whiteboard:draw', {
      whiteboard_id: boardId,
      boardId,
      ...data,
      user_id: HFState.currentUser?.id,
      userId: HFState.currentUser?.id,
      timestamp: new Date().toISOString()
    });
  },

  /**
   * Join whiteboard room
   */
  joinWhiteboard(whiteboardId) {
    this.emit('whiteboard:join', {
      whiteboard_id: whiteboardId,
      boardId: whiteboardId,
      user_id: HFState.currentUser?.id,
      userId: HFState.currentUser?.id
    });
  },

  /**
   * Leave whiteboard room
   */
  leaveWhiteboard(whiteboardId) {
    this.emit('whiteboard:leave', {
      whiteboard_id: whiteboardId,
      boardId: whiteboardId,
      user_id: HFState.currentUser?.id,
      userId: HFState.currentUser?.id
    });
  },

  /**
   * Join room
   */
  joinRoom(roomId) {
    this.emit('join', { roomId });
  },

  /**
   * Leave room
   */
  leaveRoom(roomId) {
    this.emit('leave', { roomId });
  },

  /**
   * Disconnect
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  HFSocket.init();
});

window.HFSocket = HFSocket;
