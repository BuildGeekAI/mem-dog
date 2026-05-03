import type { Config } from 'jest';
import path from 'path';

const config: Config = {
  displayName: 'ui-unit',
  testEnvironment: 'jsdom',
  
  // Root directory for tests
  rootDir: path.resolve(__dirname, '../../ui'),
  
  // Test file patterns
  testMatch: ['<rootDir>/../testing/ui/unit/**/*.test.{ts,tsx}'],
  
  // Setup files
  setupFilesAfterEnv: ['<rootDir>/../testing/ui/jest.setup.ts'],
  
  // Module resolution
  moduleNameMapper: {
    // Handle path aliases from tsconfig
    '^@/(.*)$': '<rootDir>/src/$1',
    // Handle CSS imports
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  
  // Transform TypeScript/TSX files
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        moduleResolution: 'node',
        allowSyntheticDefaultImports: true,
      },
    }],
  },
  
  // Ignore transformations for node_modules
  transformIgnorePatterns: [
    '/node_modules/',
  ],
  
  // Coverage configuration
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/app/layout.tsx',
    '!src/app/globals.css',
  ],
  
  // Module file extensions
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  
  // Clear mocks between tests
  clearMocks: true,
  
  // Verbose output
  verbose: true,
};

export default config;
