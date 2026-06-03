/**
 * Obsidian URI helpers — read-only deep-link generation only.
 *
 * Safety constraints:
 * - Only generates obsidian:// URIs. Never file://, shell://, or arbitrary paths.
 * - Vault name is derived from the last path segment only; no absolute paths leak into the URI.
 * - Relative file paths are normalized but never traversed on disk.
 * - No vault writes, no filesystem access.
 */

/**
 * Extract the vault name from a full vault path.
 * Supports both Windows backslashes and forward slashes.
 *
 * Example:
 *   "D:\\Hasnain\\...\\AI-Command-Center" → "AI-Command-Center"
 */
export function getVaultNameFromPath(vaultPath: string): string {
  const normalized = vaultPath.replace(/\\/g, '/').replace(/\/+$/, '');
  const parts = normalized.split('/').filter(Boolean);
  return parts[parts.length - 1] ?? vaultPath;
}

/**
 * Build an obsidian://open URI for a vault-relative file path.
 *
 * Example:
 *   vaultPath    = "D:\\...\\AI-Command-Center"
 *   relFilePath  = "wiki/projects/My Project.md"
 *   result       = "obsidian://open?vault=AI-Command-Center&file=wiki%2Fprojects%2FMy%20Project.md"
 *
 * @param vaultPath      - Absolute path to the vault root (from backend config).
 * @param relFilePath    - Vault-relative file path (forward or backslash, with or without leading slash).
 */
export function createObsidianOpenUrl(vaultPath: string, relFilePath: string): string {
  const vaultName = getVaultNameFromPath(vaultPath);
  const normalized = relFilePath
    .replace(/\\/g, '/')
    .replace(/^\/+/, '');
  return `obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(normalized)}`;
}
