import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DataList from '@/components/DataList';
import * as api from '@/lib/api';
import type { DataListItem } from '@/types';

// Mock the API module
jest.mock('@/lib/api');

const mockListData = api.listData as jest.MockedFunction<typeof api.listData>;
const mockFormatBytes = api.formatBytes as jest.MockedFunction<typeof api.formatBytes>;
const mockFormatDate = api.formatDate as jest.MockedFunction<typeof api.formatDate>;

// Mock useRouter
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const mockDataItems: DataListItem[] = [
  {
    data_id: 'abc12345-6789-0def-ghij-klmnopqrstuv',
    current_version: 1,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z',
    content_type: 'application/json',
    size: 1024,
  },
  {
    data_id: 'xyz98765-4321-0fed-cba0-987654321abc',
    current_version: 3,
    created_at: '2024-01-10T08:00:00Z',
    updated_at: '2024-01-14T15:45:00Z',
    content_type: 'text/plain',
    size: 512,
  },
];

describe('DataList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFormatBytes.mockImplementation((bytes) => `${bytes} Bytes`);
    mockFormatDate.mockImplementation((date) => new Date(date).toLocaleDateString());
  });

  describe('Loading State', () => {
    it('renders loading state initially', () => {
      mockListData.mockImplementation(() => new Promise(() => {})); // Never resolves
      
      render(<DataList />);
      
      expect(screen.getByText('Loading data...')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('renders empty state when no data', async () => {
      mockListData.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('No Data Yet')).toBeInTheDocument();
      });
      expect(screen.getByText('Upload your first data item to get started')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('renders error state when API fails', async () => {
      mockListData.mockRejectedValue(new Error('Network error'));
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });

    it('retries loading data when retry button is clicked', async () => {
      mockListData.mockRejectedValueOnce(new Error('Network error'));
      mockListData.mockResolvedValueOnce({ items: mockDataItems, total: mockDataItems.length, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
      
      await waitFor(() => {
        expect(screen.getByText('Stored Data')).toBeInTheDocument();
      });
      expect(mockListData).toHaveBeenCalledTimes(2);
    });
  });

  describe('Data Display', () => {
    it('renders data table with items', async () => {
      mockListData.mockResolvedValue({ items: mockDataItems, total: mockDataItems.length, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('Stored Data')).toBeInTheDocument();
      });
      
      // Check table headers
      expect(screen.getByText('Data ID')).toBeInTheDocument();
      expect(screen.getByText('Version')).toBeInTheDocument();
      expect(screen.getByText('Content Type')).toBeInTheDocument();
      expect(screen.getByText('Size')).toBeInTheDocument();
      expect(screen.getByText('Created')).toBeInTheDocument();
      expect(screen.getByText('Updated')).toBeInTheDocument();
      
      // Check data is displayed (truncated ID)
      expect(screen.getByText('abc12345...')).toBeInTheDocument();
      expect(screen.getByText('v1')).toBeInTheDocument();
      expect(screen.getByText('application/json')).toBeInTheDocument();
    });

    it('shows truncated data IDs', async () => {
      mockListData.mockResolvedValue({ items: mockDataItems, total: mockDataItems.length, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('abc12345...')).toBeInTheDocument();
        expect(screen.getByText('xyz98765...')).toBeInTheDocument();
      });
    });
  });

  describe('Interactions', () => {
    it('navigates to data detail page when row is clicked', async () => {
      mockListData.mockResolvedValue({ items: mockDataItems, total: mockDataItems.length, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('abc12345...')).toBeInTheDocument();
      });
      
      // Click on the first row
      const firstRow = screen.getByText('abc12345...').closest('tr');
      fireEvent.click(firstRow!);
      
      expect(mockPush).toHaveBeenCalledWith('/data/abc12345-6789-0def-ghij-klmnopqrstuv');
    });

    it('refreshes data when refresh button is clicked', async () => {
      mockListData.mockResolvedValue({ items: mockDataItems, total: mockDataItems.length, skip: 0, limit: 20 });
      
      render(<DataList />);
      
      await waitFor(() => {
        expect(screen.getByText('Stored Data')).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
      
      expect(mockListData).toHaveBeenCalledTimes(2);
    });
  });
});
