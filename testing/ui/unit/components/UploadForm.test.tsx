import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UploadForm from '@/components/UploadForm';
import * as api from '@/lib/api';

// Mock the API module
jest.mock('@/lib/api');

const mockCreateData = api.createData as jest.MockedFunction<typeof api.createData>;

describe('UploadForm', () => {
  const mockOnSuccess = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders the upload form with title', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      expect(screen.getByText('Upload New Data')).toBeInTheDocument();
    });

    it('renders text content mode by default', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Enter any text or JSON here/i)).toBeInTheDocument();
    });

    it('renders mode toggle buttons', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      expect(screen.getByRole('button', { name: 'Text Content' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'File Upload' })).toBeInTheDocument();
    });

    it('renders upload button', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      expect(screen.getByRole('button', { name: 'Upload Data' })).toBeInTheDocument();
    });
  });

  describe('Mode Switching', () => {
    it('switches to file upload mode when button is clicked', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      fireEvent.click(screen.getByRole('button', { name: 'File Upload' }));
      
      expect(screen.getByLabelText('Select File')).toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/Enter any text or JSON here/i)).not.toBeInTheDocument();
    });

    it('switches back to text mode when button is clicked', () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      // Switch to file mode
      fireEvent.click(screen.getByRole('button', { name: 'File Upload' }));
      expect(screen.queryByPlaceholderText(/Enter any text or JSON here/i)).not.toBeInTheDocument();
      
      // Switch back to text mode
      fireEvent.click(screen.getByRole('button', { name: 'Text Content' }));
      expect(screen.getByPlaceholderText(/Enter any text or JSON here/i)).toBeInTheDocument();
    });
  });

  describe('Text Content Submission', () => {
    it('shows error when submitting empty text content', async () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(screen.getByText('Please enter some text content')).toBeInTheDocument();
      });
      expect(mockCreateData).not.toHaveBeenCalled();
    });

    it('submits text content successfully', async () => {
      mockCreateData.mockResolvedValue({
        data_id: 'test-id',
        version: 1,
        message: 'Data created successfully',
      });
      
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      const textarea = screen.getByPlaceholderText(/Enter any text or JSON here/i);
      fireEvent.change(textarea, { target: { value: '{"test": "data"}' } });
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(mockCreateData).toHaveBeenCalledWith('{"test": "data"}');
      });
      expect(screen.getByText('Data uploaded successfully!')).toBeInTheDocument();
      expect(mockOnSuccess).toHaveBeenCalled();
    });

    it('clears form after successful submission', async () => {
      mockCreateData.mockResolvedValue({
        data_id: 'test-id',
        version: 1,
        message: 'Data created successfully',
      });
      
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      const textarea = screen.getByPlaceholderText(/Enter any text or JSON here/i);
      fireEvent.change(textarea, { target: { value: '{"test": "data"}' } });
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(textarea).toHaveValue('');
      });
    });

    it('shows error message when API fails', async () => {
      mockCreateData.mockRejectedValue(new Error('Upload failed'));
      
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      const textarea = screen.getByPlaceholderText(/Enter any text or JSON here/i);
      fireEvent.change(textarea, { target: { value: '{"test": "data"}' } });
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(screen.getByText('Upload failed')).toBeInTheDocument();
      });
      expect(mockOnSuccess).not.toHaveBeenCalled();
    });
  });

  describe('File Upload Submission', () => {
    it('shows error when submitting without selecting a file', async () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      fireEvent.click(screen.getByRole('button', { name: 'File Upload' }));
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(screen.getByText('Please select a file')).toBeInTheDocument();
      });
      expect(mockCreateData).not.toHaveBeenCalled();
    });

    it('shows selected file info', async () => {
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      fireEvent.click(screen.getByRole('button', { name: 'File Upload' }));
      
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      const input = screen.getByLabelText('Select File');
      
      Object.defineProperty(input, 'files', { value: [file] });
      fireEvent.change(input);
      
      await waitFor(() => {
        expect(screen.getByText(/Selected: test.txt/)).toBeInTheDocument();
      });
    });

    it('submits file successfully', async () => {
      mockCreateData.mockResolvedValue({
        data_id: 'test-id',
        version: 1,
        message: 'Data created successfully',
      });
      
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      fireEvent.click(screen.getByRole('button', { name: 'File Upload' }));
      
      const file = new File(['test content'], 'test.txt', { type: 'text/plain' });
      const input = screen.getByLabelText('Select File');
      
      Object.defineProperty(input, 'files', { value: [file] });
      fireEvent.change(input);
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(mockCreateData).toHaveBeenCalledWith(file);
      });
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('disables form elements while uploading', async () => {
      mockCreateData.mockImplementation(() => new Promise(() => {})); // Never resolves
      
      render(<UploadForm onSuccess={mockOnSuccess} />);
      
      const textarea = screen.getByPlaceholderText(/Enter any text or JSON here/i);
      fireEvent.change(textarea, { target: { value: 'test' } });
      
      fireEvent.click(screen.getByRole('button', { name: 'Upload Data' }));
      
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Uploading...' })).toBeDisabled();
        expect(textarea).toBeDisabled();
      });
    });
  });
});
