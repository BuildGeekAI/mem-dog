'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { Organization, Project } from '@/types';
import { listOrganizations, listProjects } from './api';
import { useAuth } from './auth-context';

interface ProjectContextType {
  orgs: Organization[];
  projects: Project[];
  selectedOrgId: string | null;
  selectedProjectId: string | null;
  setSelectedOrgId: (id: string | null) => void;
  setSelectedProjectId: (id: string | null) => void;
  loading: boolean;
  refresh: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

const LS_ORG_KEY = 'mem_dog_selected_org';
const LS_PROJECT_KEY = 'mem_dog_selected_project';

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { session, loading: authLoading } = useAuth();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedOrgId, setSelectedOrgIdRaw] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectIdRaw] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);

  const setSelectedOrgId = useCallback((id: string | null) => {
    setSelectedOrgIdRaw(id);
    if (id) {
      localStorage.setItem(LS_ORG_KEY, id);
    } else {
      localStorage.removeItem(LS_ORG_KEY);
    }
    // Reset project when org changes
    setSelectedProjectIdRaw(null);
    localStorage.removeItem(LS_PROJECT_KEY);
  }, []);

  const setSelectedProjectId = useCallback((id: string | null) => {
    setSelectedProjectIdRaw(id);
    if (id) {
      localStorage.setItem(LS_PROJECT_KEY, id);
    } else {
      localStorage.removeItem(LS_PROJECT_KEY);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const orgRes = await listOrganizations();
      setOrgs(orgRes.organizations);

      // Restore from localStorage or pick first
      const savedOrg = localStorage.getItem(LS_ORG_KEY);
      const orgId = orgRes.organizations.find(o => o.org_id === savedOrg)?.org_id
        || orgRes.organizations[0]?.org_id
        || null;
      setSelectedOrgIdRaw(orgId);

      if (orgId) {
        const projRes = await listProjects(orgId);
        setProjects(projRes.projects);

        const savedProj = localStorage.getItem(LS_PROJECT_KEY);
        const projId = projRes.projects.find(p => p.project_id === savedProj)?.project_id
          || projRes.projects[0]?.project_id
          || null;
        setSelectedProjectIdRaw(projId);
      }
    } catch (err) {
      console.warn('[ProjectContext] Failed to load orgs/projects:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load projects when org changes (but not on initial load — refresh handles that)
  useEffect(() => {
    if (!initialized || !selectedOrgId) {
      if (!selectedOrgId) setProjects([]);
      return;
    }
    listProjects(selectedOrgId).then(res => {
      setProjects(res.projects);
      const savedProj = localStorage.getItem(LS_PROJECT_KEY);
      const projId = res.projects.find(p => p.project_id === savedProj)?.project_id
        || res.projects[0]?.project_id
        || null;
      setSelectedProjectIdRaw(projId);
    }).catch(() => setProjects([]));
  }, [selectedOrgId, initialized]);

  // Load orgs/projects once auth is ready
  // For non-Supabase setups (no session), load immediately once authLoading is done
  useEffect(() => {
    if (authLoading) return;

    const supabaseConfigured = !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    // If Supabase is configured but no session, don't load (user needs to log in)
    if (supabaseConfigured && !session) {
      setLoading(false);
      return;
    }

    // Auth ready — load orgs
    refresh().then(() => setInitialized(true));
  }, [authLoading, session, refresh]);

  return (
    <ProjectContext.Provider value={{
      orgs, projects, selectedOrgId, selectedProjectId,
      setSelectedOrgId, setSelectedProjectId, loading, refresh,
    }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used within ProjectProvider');
  return ctx;
}
