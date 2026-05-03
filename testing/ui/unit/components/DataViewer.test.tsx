import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DataViewer from '@/components/DataViewer';
import * as api from '@/lib/api';
import type { DataMetadata } from '@/types';

// Mock the API module
jest.mock('@/lib/api');

const mockGetDataAsText = api.getDataAsText as jest.MockedFunction<typeof api.getDataAsText>;
const mockGetData = api.getData as jest.MockedFunction<typeof api.getData>;
const mockUpdateData = api.updateData as jest.MockedFunction<typeof api.updateData>;
const mockDeleteData = api.deleteData as jest.MockedFunction<typeof api.deleteData>;

const mockMetadata: DataMetadata = {
  data_id: 'test-data-id',
  current_version: 2,
  versions: [
    {
      version: 1,
      timestamp: '2024-01-15T10:30:00Z',
      size: 100,
      content_type: 'application/json',
    },
    {
      version: 2,
      timestamp: '2024-01-16T14:45:00Z',
      size: 150,
      content_type: 'application/json',
    },
  ],
  created_at: '2024-01-15T10:30:00Z',
  updated_at: '2024-01-16T14:45:00Z',
};

const mockBinaryMetadata: DataMetadata = {
  data_id: 'binary-data-id',
  current_version: 1,
  versions: [
    {
      version: 1,
      timestamp: '2024-01-15T10:30:00Z',
      size: 1024,
      content_type: 'image/png',
    },
  ],
  created_at: '2024-01-15T10:30:00Z',
  updated_at: '2024-01-15T10:30:00Z',
};

describe('DataViewer', () => {
  const mockOnUpdate = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('renders loading state while fetching content', () => {
      mockGetDataAsText.mockImplementation(() => new Promise(() => {})); // Never resolves
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      expect(screen.getByText('Loading content...')).toBeInTheDocument();
    });
  });

  describe('Text Content Display', () => {
    it('renders text content correctly', async () => {
      mockGetDataAsText.mockResolvedValue('{"test": "data"}');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText('{"test": "data"}')).toBeInTheDocument();
      });
    });

    it('displays version number in header', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText(/Content.*\(v2\)/)).toBeInTheDocument();
      });
    });
  });

  describe('Edit Mode (Current Version)', () => {
    it('shows edit button for current version', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
      });
    });

    it('shows delete button for current version', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
      });
    });

    it('enters edit mode when edit button is clicked', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toHaveValue('test content');
    });

    it('cancels edit mode when cancel button is clicked', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      
      expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    });

    it('saves changes when save button is clicked', async () => {
      mockGetDataAsText.mockResolvedValue('original content');
      mockUpdateData.mockResolvedValue({
        data_id: 'test-data-id',
        version: 3,
        message: 'Data updated successfully',
      });
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      });
      
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'updated content' } });
      
      fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
      
      await waitFor(() => {
        expect(mockUpdateData).toHaveBeenCalledWith('test-data-id', 'updated content');
        expect(mockOnUpdate).toHaveBeenCalled();
      });
      expect(screen.getByText('Data updated successfully!')).toBeInTheDocument();
    });
  });

  describe('Old Version (Read-only)', () => {
    it('shows read-only indicator for old versions', async () => {
      mockGetDataAsText.mockResolvedValue('old content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={1}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText('(Read-only - old version)')).toBeInTheDocument();
      });
    });

    it('does not show edit button for old versions', async () => {
      mockGetDataAsText.mockResolvedValue('old content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={1}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
      });
    });

    it('does not show delete button for old versions', async () => {
      mockGetDataAsText.mockResolvedValue('old content');
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={1}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
      });
    });
  });

  describe('Delete Functionality', () => {
    it('calls onDelete when delete is confirmed', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      mockDeleteData.mockResolvedValue(undefined);
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
      });
      
      await waitFor(() => {
        expect(mockDeleteData).toHaveBeenCalledWith('test-data-id');
        expect(mockOnDelete).toHaveBeenCalled();
      });
    });
  });

  describe('Binary Content', () => {
    it('renders binary content message for non-text files', async () => {
      mockGetData.mockResolvedValue(new Blob(['binary'], { type: 'image/png' }));
      
      render(
        <DataViewer
          dataId="binary-data-id"
          version={1}
          metadata={mockBinaryMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText(/This is a binary file/)).toBeInTheDocument();
        expect(screen.getByText('image/png')).toBeInTheDocument();
      });
    });

    it('shows download button for binary content', async () => {
      mockGetData.mockResolvedValue(new Blob(['binary'], { type: 'image/png' }));
      
      render(
        <DataViewer
          dataId="binary-data-id"
          version={1}
          metadata={mockBinaryMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText('Download File')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error when content fails to load', async () => {
      mockGetDataAsText.mockRejectedValue(new Error('Failed to load content'));
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText('Failed to load content')).toBeInTheDocument();
      });
    });

    it('displays error when update fails', async () => {
      mockGetDataAsText.mockResolvedValue('test content');
      mockUpdateData.mockRejectedValue(new Error('Update failed'));
      
      render(
        <DataViewer
          dataId="test-data-id"
          version={2}
          metadata={mockMetadata}
          onUpdate={mockOnUpdate}
          onDelete={mockOnDelete}
        />
      );
      
      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
      });
      
      fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
      
      await waitFor(() => {
        expect(screen.getByText('Update failed')).toBeInTheDocument();
      });
    });
  });
});
