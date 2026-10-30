from .public import TelegramChannel, VisaCatcher, Vizetakip
from .vfs_flags import VfsFlags

PROVIDERS = [Vizetakip(), VisaCatcher(), TelegramChannel(), VfsFlags()]
