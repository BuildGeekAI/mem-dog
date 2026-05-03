import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import Timeline from '@/components/Timeline';
import * as api from '@/lib/api';
import type { TimelineEntry } from '@/types';

// Mock the API module
jest.mock('@/lib/api');

const mockGetTimeline = api.getTimeline as jest.MockedFunction<typeof api.getTimeline>;
const mockFormatTimestamp = api.formatTimestamp as jest.MockedFunction<typeof api.formatTimestamp>;

const mockTimelineEntries: TimelineEntry[] = [
  {
    user: 'test-user',
    data_id: 'abc12345-6789-0def-ghij-klmnopqrstuv',
    version: 1,
    action: 'create',
    timestamp: 1705315800,
  },
  {
    user: 'test-user',
    data_id: 'abc12345-6789-0def-ghij-klmnopqrstuv',
    version: 2,
    action: 'update',
    timestamp: 1705319400,
  },
  {
    user: 'admin',
    data_id: 'xyz98765-4321-0fed-cba0-987654321abc',
    version: 1,
    action: 'delete',
    timestamp: 1705323000,
  },
];

describe('Timeline', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFormatTimestamp.mockImplementation((ts) => new Date(ts * 1000).toLocaleString());
  });

  describe('Loading State', () => {
    it('renders loading state initially', () => {
      mockGetTimeline.mockImplementation(() => new Promise(() => {})); // Never resolves
      
      render(<Timeline />);
      
      expect(screen.getByText('Loading timeline...')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('renders empty state when no timeline entries', async () => {
      mockGetTimeline.mockResolvedValue([]);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('No Activity Yet')).toBeInTheDocument();
      });
      expect(screen.getByText('Timeline will show all data operations')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('renders error state when API fails', async () => {
      mockGetTimeline.mockRejectedValue(new Error('Failed to fetch timeline'));
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('Failed to fetch timeline')).toBeInTheDocument();
      });
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });

    it('retries loading when retry button is clicked', async () => {
      mockGetTimeline.mockRejectedValueOnce(new Error('Network error'));
      mockGetTimeline.mockResolvedValueOnce(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
      
      await waitFor(() => {
        expect(screen.getByText('Activity Timeline')).toBeInTheDocument();
      });
      expect(mockGetTimeline).toHaveBeenCalledTimes(2);
    });
  });

  describe('Timeline Display', () => {
    it('renders timeline entries', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('Activity Timeline')).toBeInTheDocument();
      });
      
      // Check action labels
      expect(screen.getByText('Create')).toBeInTheDocument();
      expect(screen.getByText('Update')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('displays user information', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getAllByText('test-user')).toHaveLength(2);
        expect(screen.getByText('admin')).toBeInTheDocument();
      });
    });

    it('displays version information', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getAllByText('v1')).toHaveLength(2);
        expect(screen.getByText('v2')).toBeInTheDocument();
      });
    });

    it('shows truncated data IDs', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        // Check for truncated data IDs (first 16 chars + ...)
        expect(screen.getAllByText(/abc12345-6789-0d\.\.\./)).toHaveLength(2);
        expect(screen.getByText(/xyz98765-4321-0f\.\.\./)).toBeInTheDocument();
      });
    });

    it('shows view link for non-delete actions', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        // Should have 2 "View Data" links (create and update, not delete)
        const viewLinks = screen.getAllByText('View Data →');
        expect(viewLinks).toHaveLength(2);
      });
    });

    it('does not show view link for delete actions', async () => {
      mockGetTimeline.mockResolvedValue([
        {
          user: 'admin',
          data_id: 'deleted-data-id-12345678',
          version: 1,
          action: 'delete',
          timestamp: 1705323000,
        },
      ]);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument();
      });
      
      expect(screen.queryByText('View Data →')).not.toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('refreshes timeline when refresh button is clicked', async () => {
      mockGetTimeline.mockResolvedValue(mockTimelineEntries);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('Activity Timeline')).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
      
      expect(mockGetTimeline).toHaveBeenCalledTimes(2);
    });
  });

  describe('Action Icons and Colors', () => {
    it('displays correct icon for create action', async () => {
      mockGetTimeline.mockResolvedValue([mockTimelineEntries[0]]);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('+')).toBeInTheDocument();
      });
    });

    it('displays correct icon for update action', async () => {
      mockGetTimeline.mockResolvedValue([mockTimelineEntries[1]]);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('↻')).toBeInTheDocument();
      });
    });

    it('displays correct icon for delete action', async () => {
      mockGetTimeline.mockResolvedValue([mockTimelineEntries[2]]);
      
      render(<Timeline />);
      
      await waitFor(() => {
        expect(screen.getByText('×')).toBeInTheDocument();
      });
    });
  });
});
