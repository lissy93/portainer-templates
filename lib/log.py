# lib/log.py — shared colored / CI-aware logger for all lib scripts
import logging
import os
import sys

RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
TEAL = '\033[38;2;38;198;218m'
LEVEL_COLORS = {
  'DEBUG': (128, 128, 128),
  'INFO': (80, 180, 250),
  'WARNING': (255, 165, 0),
  'ERROR': (255, 60, 60),
  'CRITICAL': (255, 60, 60),
}
GH_PREFIX = {'DEBUG': '::debug::', 'WARNING': '::warning::', 'ERROR': '::error::', 'CRITICAL': '::error::'}
_CONFIGURED = set()

def _rgb(rgb):
  r, g, b = rgb
  return f'\033[38;2;{r};{g};{b}m'

class Formatter(logging.Formatter):
  """Colorize the level on a TTY, emit GitHub Actions annotations in CI, else plain."""
  def __init__(self, color, github):
    super().__init__()
    self.color = color
    self.github = github

  def format(self, record):
    msg = record.getMessage()
    level = record.levelname
    if record.exc_info:
      msg = f'{msg}\n{self.formatException(record.exc_info)}'
    if self.github and level in GH_PREFIX:
      # extra={'annotate': {'file': ..., 'line': ...}} pins it to a line of the PR
      where = ','.join(f'{key}={value}' for key, value in getattr(record, 'annotate', {}).items())
      prefix = f'{GH_PREFIX[level][:-2]} {where}::' if where else GH_PREFIX[level]
      return f'{prefix}{msg}'
    tag = f'[{level}]'
    if self.color and level in LEVEL_COLORS:
      tag = f'{_rgb(LEVEL_COLORS[level])}{tag}{RESET}'
    return f'{tag} {msg}'

def _color_enabled(github):
  """Enable ANSI when forced, or on a real TTY outside CI"""
  if os.environ.get('NO_COLOR'):
    return False
  if os.environ.get('FORCE_COLOR'):
    return True
  if github:
    return False
  return sys.stderr.isatty()

def banner(title, description=''):
  """Print a pretty title and description at start of each job"""
  color = _color_enabled(bool(os.environ.get('GITHUB_ACTIONS')))
  c, end = (TEAL, RESET) if color else ('', '')
  rows = [(title, BOLD), (description, DIM)] if description else [(title, BOLD)]
  width = max(len(text) for text, _ in rows)
  out = [f'{c}╭{"─" * (width + 2)}╮{end}']
  for text, style in rows:
    body = f'{TEAL}{style}{text}{RESET}' if color else text
    out.append(f'{c}│{end} {body}{" " * (width - len(text))} {c}│{end}')
  out.append(f'{c}╰{"─" * (width + 2)}╯{end}')
  sys.stderr.write('\n'.join(out) + '\n')

def get_logger(name='lib'):
  """Return an idempotently-configured logger writing to stderr; level from LOG_LEVEL."""
  logger = logging.getLogger(name)
  if name in _CONFIGURED:
    return logger
  level = os.environ.get('LOG_LEVEL', 'INFO').upper()
  logger.setLevel(getattr(logging, level, logging.INFO))
  github = bool(os.environ.get('GITHUB_ACTIONS'))
  handler = logging.StreamHandler(sys.stderr)
  handler.setFormatter(Formatter(_color_enabled(github), github))
  logger.addHandler(handler)
  logger.propagate = False
  _CONFIGURED.add(name)
  return logger
