import snarkdown from 'snarkdown';

export const slugify = (title: string): string =>
  title.toLowerCase().replace(/[^a-zA-Z ]/g, '').replaceAll(' ', '-');

// "Airsonic (container)" -> "Airsonic"
export const baseTitle = (title: string): string =>
  title.replace(/\s*\((?:container|stack|swarm|compose|edge)\)\s*$/i, '');

// A variant that another entry stands in for in listings (eg the stack, when the container's shown)
export const isHiddenVariant = (slug: string, primary?: string): boolean => !!primary && primary !== slug;

// Title for listings, dropping the variant suffix on the entry that stands in for them all
export const listingTitle = (title: string, primary?: string): string =>
  primary === slugify(title) ? baseTitle(title) : title;

const markdownPattern = /\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|~~[^~]+~~/;

// Parse markdown descriptions, dropping links to their label (cards are already links). Null if plaintext.
export const parseDescription = (text: string): string | null =>
  markdownPattern.test(text) ? snarkdown(text).replace(/<\/?a[^>]*>/gi, '') : null;

export const formatBigNumber = (num: number): string => {
  if (!num) return '';
  const units = ['k', 'M', 'B'];
  let unitIndex = 0;
  let value = num;
  while (value >= 1000 && unitIndex < units.length) {
    value /= 1000;
    unitIndex++;
  }
  const decimals = num < 10000 || (num >= 100000 && num < 1000000) ? 0 : 1;
  return num < 1000 ? num.toString() : value.toFixed(decimals) + units[unitIndex - 1];
};

export const formatBytes = (bytes: number | null): string => {
  if (!bytes) return '';
  const mb = bytes / 1048576;
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
};

export const formatDate = (dateTime: string): string => {
  if (!dateTime) return '';
  const date = new Date(dateTime);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'short', day: '2-digit' }).format(date);
};

export const timeAgo = (dateTime: string): string => {
  if (!dateTime) return '';
  const time = new Date(dateTime).getTime();
  if (Number.isNaN(time)) return '';
  const elapsed = Date.now() - time;
  if (elapsed < 0) return 'just now';
  const msPer = [60000, 3600000, 86400000, 2592000000, 31536000000];
  const units = ['minute', 'hour', 'day', 'month', 'year'];

  for (let i = 0; i < msPer.length; i++) {
    if (elapsed < msPer[i]) {
      if (i === 0) return 'just now';
      const value = Math.floor(elapsed / msPer[i - 1]);
      return `${value} ${units[i - 1]}${value > 1 ? 's' : ''} ago`;
    }
  }
  return `${Math.floor(elapsed / msPer[4])} years ago`;
};

// Render project docs (Docker Hub / GitHub readmes) with a few GFM niceties snarkdown misses.
export const renderDoc = (md: string | null | undefined): string => {
  if (!md) return '';

  // GitHub-flavoured bits snarkdown lacks: pipe tables, bare video links, over-long break runs
  const FENCE = /^```[\s\S]*?^```/gm;
  const BR_RUN = /(?:<br\s*\/?>[ \t]*){3,}/gi;
  const VIDEO = /^[ \t]*(https?:\/\/\S+\.(?:mp4|webm|ogg|mov))[ \t]*$/gim;
  const TABLE = /^ {0,3}\|(.+)\|[ \t]*\n {0,3}\|[ :|-]+\|[ \t]*\n((?: {0,3}\|.*\|[ \t]*(?:\n|$))+)/gm;
  const STASH = /\[\[\[fence:(\d+)\]\]\]/g;

  const cells = (row: string): string[] =>
    row.replace(/^ *\|[ \t]*|[ \t]*\|[ \t]*$/g, '').split('|').map((c) => c.trim());

  // one GFM pipe table to an HTML table, rendering each cell's inline markdown
  const toTable = (_m: string, head: string, body: string): string => {
    const th = cells(head).map((c) => `<th>${snarkdown(c)}</th>`).join('');
    const rows = body
      .trimEnd()
      .split('\n')
      .map((r) => `<tr>${cells(r).map((c) => `<td>${snarkdown(c)}</td>`).join('')}</tr>`)
      .join('');
    return `\n<table><thead><tr>${th}</tr></thead><tbody>${rows}</tbody></table>\n`;
  };

  // stash fenced code behind a placeholder so its contents survive the transforms untouched
  const fences: string[] = [];
  const prepared = md
    .replace(/\r\n?/g, '\n')
    .replace(FENCE, (m) => `[[[fence:${fences.push(m) - 1}]]]`)
    .replace(BR_RUN, '<br><br>')
    .replace(VIDEO, (_m, url) => `\n<video controls preload="metadata" src="${url}"></video>\n`)
    .replace(TABLE, toTable)
    .replace(STASH, (_m, i) => fences[+i]);
  return snarkdown(prepared);
};
