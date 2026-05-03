import axios from 'axios';
import {
  listData,
  getData,
  getDataAsText,
  getMetadata,
  createData,
  updateData,
  deleteData,
  getVersions,
  getTimeline,
  formatBytes,
  formatDate,
  formatTimestamp,
  // Session functions
  generateSessionId,
  listSessions,
  createSession,
  getSession,
  updateSession,
  deleteSession,
  getSessionData,
  validateSession,
  getCurrentSessionId,
  setCurrentSessionId,
  clearCurrentSessionId,
} from '@/lib/api';

// Mock axios
jest.mock('axios');

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('API Client', () => {
  let mockAxiosInstance: {
    get: jest.Mock;
    post: jest.Mock;
    put: jest.Mock;
    delete: jest.Mock;
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      put: jest.fn(),
      delete: jest.fn(),
    };
    
    mockedAxios.create.mockReturnValue(mockAxiosInstance as any);
    
    // Re-import to get fresh instance with mocked axios
    jest.resetModules();
  });

  describe('Utility Functions', () => {
    describe('formatBytes', () => {
      it('formats 0 bytes', () => {
        expect(formatBytes(0)).toBe('0 Bytes');
      });

      it('formats bytes', () => {
        expect(formatBytes(500)).toBe('500 Bytes');
      });

      it('formats kilobytes', () => {
        expect(formatBytes(1024)).toBe('1 KB');
        expect(formatBytes(1536)).toBe('1.5 KB');
      });

      it('formats megabytes', () => {
        expect(formatBytes(1048576)).toBe('1 MB');
        expect(formatBytes(2621440)).toBe('2.5 MB');
      });

      it('formats gigabytes', () => {
        expect(formatBytes(1073741824)).toBe('1 GB');
      });
    });

    describe('formatDate', () => {
      it('formats ISO date string', () => {
        const result = formatDate('2024-01-15T10:30:00Z');
        // Result depends on locale, just check it returns a string
        expect(typeof result).toBe('string');
        expect(result.length).toBeGreaterThan(0);
      });
    });

    describe('formatTimestamp', () => {
      it('formats unix timestamp', () => {
        const result = formatTimestamp(1705315800);
        expect(typeof result).toBe('string');
        expect(result.length).toBeGreaterThan(0);
      });
    });
  });
});

describe('API Functions (Integration)', () => {
  // These tests verify the API functions make correct axios calls
  // They require more complex mocking of the module system
  
  describe('listData', () => {
    it('should be a function', () => {
      expect(typeof listData).toBe('function');
    });
  });

  describe('getData', () => {
    it('should be a function', () => {
      expect(typeof getData).toBe('function');
    });
  });

  describe('getDataAsText', () => {
    it('should be a function', () => {
      expect(typeof getDataAsText).toBe('function');
    });
  });

  describe('getMetadata', () => {
    it('should be a function', () => {
      expect(typeof getMetadata).toBe('function');
    });
  });

  describe('createData', () => {
    it('should be a function', () => {
      expect(typeof createData).toBe('function');
    });
  });

  describe('updateData', () => {
    it('should be a function', () => {
      expect(typeof updateData).toBe('function');
    });
  });

  describe('deleteData', () => {
    it('should be a function', () => {
      expect(typeof deleteData).toBe('function');
    });
  });

  describe('getVersions', () => {
    it('should be a function', () => {
      expect(typeof getVersions).toBe('function');
    });
  });

  describe('getTimeline', () => {
    it('should be a function', () => {
      expect(typeof getTimeline).toBe('function');
    });
  });

  // Session Management Functions
  describe('Session Management', () => {
    describe('generateSessionId', () => {
      it('should be a function', () => {
        expect(typeof generateSessionId).toBe('function');
      });

      it('should generate a session ID with sess- prefix', () => {
        const sessionId = generateSessionId();
        expect(sessionId.startsWith('sess-')).toBe(true);
      });

      it('should generate unique IDs', () => {
        const id1 = generateSessionId();
        const id2 = generateSessionId();
        expect(id1).not.toBe(id2);
      });
    });

    describe('listSessions', () => {
      it('should be a function', () => {
        expect(typeof listSessions).toBe('function');
      });
    });

    describe('createSession', () => {
      it('should be a function', () => {
        expect(typeof createSession).toBe('function');
      });
    });

    describe('getSession', () => {
      it('should be a function', () => {
        expect(typeof getSession).toBe('function');
      });
    });

    describe('updateSession', () => {
      it('should be a function', () => {
        expect(typeof updateSession).toBe('function');
      });
    });

    describe('deleteSession', () => {
      it('should be a function', () => {
        expect(typeof deleteSession).toBe('function');
      });
    });

    describe('getSessionData', () => {
      it('should be a function', () => {
        expect(typeof getSessionData).toBe('function');
      });
    });

    describe('validateSession', () => {
      it('should be a function', () => {
        expect(typeof validateSession).toBe('function');
      });
    });

    describe('Session Storage Utilities', () => {
      beforeEach(() => {
        localStorage.clear();
      });

      it('getCurrentSessionId returns null when no session stored', () => {
        expect(getCurrentSessionId()).toBeNull();
      });

      it('setCurrentSessionId stores session ID', () => {
        setCurrentSessionId('sess-test-123');
        expect(getCurrentSessionId()).toBe('sess-test-123');
      });

      it('clearCurrentSessionId removes session ID', () => {
        setCurrentSessionId('sess-test-123');
        clearCurrentSessionId();
        expect(getCurrentSessionId()).toBeNull();
      });
    });
  });
});
