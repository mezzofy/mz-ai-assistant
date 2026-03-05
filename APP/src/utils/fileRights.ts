import {FileScope} from '../api/files';

// UserInfo shape from auth.ts
interface MinimalUser {
  department?: string;
}

/**
 * Returns true if the current user has write access to the given scope.
 *
 * Access rules:
 *   personal   — always (it's their own space)
 *   department — always (any dept member can write)
 *   company    — only Management department
 */
export const canWrite = (scope: FileScope, user: MinimalUser | null): boolean => {
  if (!user) { return false; }
  if (scope === 'personal' || scope === 'department') { return true; }
  if (scope === 'company') {
    return (user.department ?? '').toLowerCase() === 'management';
  }
  return false;
};
