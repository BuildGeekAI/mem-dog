'use client';

import { useState, useEffect } from 'react';
import { AccessControl as AccessControlType } from '@/types';

interface AccessControlProps {
  dataId: string;
  access: AccessControlType;
  onUpdate?: (access: AccessControlType) => void;
  apiBaseUrl: string;
  readOnly?: boolean;
}

interface AccessEntry {
  type: 'user' | 'role' | 'wildcard';
  value: string;
}

export function AccessControl({ dataId, access, onUpdate, apiBaseUrl, readOnly = false }: AccessControlProps) {
  const [entries, setEntries] = useState<AccessEntry[]>([]);
  const [newEntry, setNewEntry] = useState({ type: 'user' as 'user' | 'role', value: '' });
  const [isPublic, setIsPublic] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Parse access control list into entries
  useEffect(() => {
    if (!access || access.length === 0) {
      setIsPublic(true);
      setEntries([]);
    } else if (access.includes('*')) {
      setIsPublic(false);
      setEntries([{ type: 'wildcard', value: '*' }]);
    } else {
      setIsPublic(false);
      const parsed = access.map(entry => {
        if (entry.startsWith('user:')) {
          return { type: 'user' as const, value: entry.substring(5) };
        } else if (entry.startsWith('role:')) {
          return { type: 'role' as const, value: entry.substring(5) };
        }
        return { type: 'user' as const, value: entry };
      });
      setEntries(parsed);
    }
  }, [access]);

  const handleSave = async (newAccess: AccessControlType) => {
    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/data/${dataId}/access`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access: newAccess })
      });
      
      if (!response.ok) {
        throw new Error('Failed to update access');
      }
      
      if (onUpdate) {
        onUpdate(newAccess);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handlePublicToggle = () => {
    const newIsPublic = !isPublic;
    setIsPublic(newIsPublic);
    
    if (newIsPublic) {
      setEntries([]);
      handleSave(null);
    }
  };

  const handleAllUsersToggle = () => {
    const hasWildcard = entries.some(e => e.type === 'wildcard');
    if (hasWildcard) {
      const newEntries = entries.filter(e => e.type !== 'wildcard');
      setEntries(newEntries);
      handleSave(newEntries.length === 0 ? null : newEntries.map(e => `${e.type}:${e.value}`));
    } else {
      const newEntries = [{ type: 'wildcard' as const, value: '*' }, ...entries.filter(e => e.type !== 'wildcard')];
      setEntries(newEntries);
      handleSave(['*']);
    }
  };

  const handleAddEntry = () => {
    if (!newEntry.value.trim()) return;
    
    const entry: AccessEntry = { type: newEntry.type, value: newEntry.value.trim() };
    const newEntries = [...entries.filter(e => e.type !== 'wildcard'), entry];
    setEntries(newEntries);
    setNewEntry({ type: 'user', value: '' });
    setIsPublic(false);
    
    const accessList = newEntries.map(e => e.type === 'wildcard' ? '*' : `${e.type}:${e.value}`);
    handleSave(accessList);
  };

  const handleRemoveEntry = (index: number) => {
    const newEntries = entries.filter((_, i) => i !== index);
    setEntries(newEntries);
    
    if (newEntries.length === 0) {
      setIsPublic(true);
      handleSave(null);
    } else {
      const accessList = newEntries.map(e => e.type === 'wildcard' ? '*' : `${e.type}:${e.value}`);
      handleSave(accessList);
    }
  };

  const getAccessLabel = () => {
    if (isPublic || !access || access.length === 0) {
      return 'Public';
    }
    if (access.includes('*')) {
      return 'All Users';
    }
    return `${access.length} ${access.length === 1 ? 'entry' : 'entries'}`;
  };

  const getAccessIcon = () => {
    if (isPublic || !access || access.length === 0) {
      return '🌍';
    }
    if (access.includes('*')) {
      return '👥';
    }
    return '🔒';
  };

  if (readOnly) {
    return (
      <div className="access-control-badge">
        <span className="access-icon">{getAccessIcon()}</span>
        <span className="access-label">{getAccessLabel()}</span>
        
        <style jsx>{`
          .access-control-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            background: #f3f4f6;
            border-radius: 4px;
            font-size: 12px;
            color: #6b7280;
          }
          .access-icon {
            font-size: 14px;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="access-control">
      <div className="access-header">
        <h4>Access Control</h4>
        <span className="access-badge">
          {getAccessIcon()} {getAccessLabel()}
        </span>
      </div>

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="access-options">
        <label className="access-option">
          <input
            type="radio"
            checked={isPublic}
            onChange={handlePublicToggle}
            disabled={saving}
          />
          <div className="option-content">
            <span className="option-icon">🌍</span>
            <div>
              <strong>Public</strong>
              <p>Anyone can access this data</p>
            </div>
          </div>
        </label>

        <label className="access-option">
          <input
            type="radio"
            checked={!isPublic && entries.some(e => e.type === 'wildcard')}
            onChange={handleAllUsersToggle}
            disabled={saving}
          />
          <div className="option-content">
            <span className="option-icon">👥</span>
            <div>
              <strong>All Authenticated Users</strong>
              <p>Any logged-in user can access</p>
            </div>
          </div>
        </label>

        <label className="access-option">
          <input
            type="radio"
            checked={!isPublic && !entries.some(e => e.type === 'wildcard')}
            onChange={() => {
              if (isPublic || entries.some(e => e.type === 'wildcard')) {
                setIsPublic(false);
                setEntries([]);
              }
            }}
            disabled={saving}
          />
          <div className="option-content">
            <span className="option-icon">🔒</span>
            <div>
              <strong>Restricted</strong>
              <p>Only specific users or roles</p>
            </div>
          </div>
        </label>
      </div>

      {!isPublic && !entries.some(e => e.type === 'wildcard') && (
        <div className="access-entries">
          <h5>Allowed Users &amp; Roles</h5>
          
          {entries.filter(e => e.type !== 'wildcard').length === 0 ? (
            <p className="empty-state">No users or roles added. Data is currently inaccessible.</p>
          ) : (
            <ul className="entry-list">
              {entries.filter(e => e.type !== 'wildcard').map((entry, index) => (
                <li key={index} className="entry-item">
                  <span className="entry-type">{entry.type === 'user' ? '👤' : '🎭'}</span>
                  <span className="entry-value">
                    <span className="type-label">{entry.type}:</span>
                    {entry.value}
                  </span>
                  <button 
                    className="remove-btn"
                    onClick={() => handleRemoveEntry(index)}
                    disabled={saving}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="add-entry">
            <select
              value={newEntry.type}
              onChange={e => setNewEntry({ ...newEntry, type: e.target.value as 'user' | 'role' })}
              disabled={saving}
            >
              <option value="user">User ID</option>
              <option value="role">Role</option>
            </select>
            <input
              type="text"
              placeholder={newEntry.type === 'user' ? 'Enter user ID...' : 'Enter role name (admin, user, viewer)...'}
              value={newEntry.value}
              onChange={e => setNewEntry({ ...newEntry, value: e.target.value })}
              onKeyDown={e => e.key === 'Enter' && handleAddEntry()}
              disabled={saving}
            />
            <button onClick={handleAddEntry} disabled={saving || !newEntry.value.trim()}>
              Add
            </button>
          </div>
        </div>
      )}

      {saving && <div className="saving-indicator">Saving...</div>}

      <style jsx>{`
        .access-control {
          padding: 16px;
          background: #f9fafb;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
        }

        .access-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .access-header h4 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
        }

        .access-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          font-size: 12px;
        }

        .error-message {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 8px 12px;
          border-radius: 4px;
          margin-bottom: 12px;
          font-size: 13px;
        }

        .access-options {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 16px;
        }

        .access-option {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 12px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          cursor: pointer;
          transition: border-color 0.2s, background 0.2s;
        }

        .access-option:hover {
          border-color: #d1d5db;
        }

        .access-option input {
          margin-top: 2px;
        }

        .access-option input:checked + .option-content {
          color: #2563eb;
        }

        .option-content {
          display: flex;
          align-items: flex-start;
          gap: 8px;
        }

        .option-icon {
          font-size: 20px;
        }

        .option-content strong {
          display: block;
          font-size: 14px;
        }

        .option-content p {
          margin: 2px 0 0;
          font-size: 12px;
          color: #6b7280;
        }

        .access-entries {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          padding: 12px;
        }

        .access-entries h5 {
          margin: 0 0 12px;
          font-size: 13px;
          font-weight: 600;
        }

        .empty-state {
          color: #ef4444;
          font-size: 13px;
          font-style: italic;
          margin: 8px 0;
        }

        .entry-list {
          list-style: none;
          padding: 0;
          margin: 0 0 12px;
        }

        .entry-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px;
          background: #f9fafb;
          border-radius: 4px;
          margin-bottom: 4px;
        }

        .entry-type {
          font-size: 16px;
        }

        .entry-value {
          flex: 1;
          font-size: 13px;
          font-family: monospace;
        }

        .type-label {
          color: #6b7280;
        }

        .remove-btn {
          background: none;
          border: none;
          color: #dc2626;
          font-size: 18px;
          cursor: pointer;
          padding: 0 4px;
        }

        .remove-btn:hover {
          color: #b91c1c;
        }

        .add-entry {
          display: flex;
          gap: 8px;
        }

        .add-entry select {
          padding: 6px 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 13px;
        }

        .add-entry input {
          flex: 1;
          padding: 6px 10px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          font-size: 13px;
        }

        .add-entry button {
          padding: 6px 12px;
          background: #2563eb;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
        }

        .add-entry button:hover:not(:disabled) {
          background: #1d4ed8;
        }

        .add-entry button:disabled {
          background: #9ca3af;
          cursor: not-allowed;
        }

        .saving-indicator {
          text-align: center;
          color: #6b7280;
          font-size: 12px;
          margin-top: 8px;
        }
      `}</style>
    </div>
  );
}

// Compact badge component for displaying access in lists
export function AccessBadge({ access }: { access: AccessControlType }) {
  const getLabel = () => {
    if (!access || access.length === 0) return 'Public';
    if (access.includes('*')) return 'All Users';
    return `${access.length} ${access.length === 1 ? 'entry' : 'entries'}`;
  };

  const getIcon = () => {
    if (!access || access.length === 0) return '🌍';
    if (access.includes('*')) return '👥';
    return '🔒';
  };

  const getColor = () => {
    if (!access || access.length === 0) return '#10b981'; // green
    if (access.includes('*')) return '#3b82f6'; // blue
    return '#f59e0b'; // amber
  };

  return (
    <span className="access-badge" title={`Access: ${getLabel()}`}>
      <span className="icon">{getIcon()}</span>
      <span className="label">{getLabel()}</span>
      
      <style jsx>{`
        .access-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 2px 6px;
          background: ${getColor()}15;
          border: 1px solid ${getColor()}30;
          border-radius: 4px;
          font-size: 11px;
          color: ${getColor()};
        }
        .icon {
          font-size: 12px;
        }
        .label {
          font-weight: 500;
        }
      `}</style>
    </span>
  );
}

export default AccessControl;
